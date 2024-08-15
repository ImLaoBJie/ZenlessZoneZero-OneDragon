from concurrent.futures import ThreadPoolExecutor, Future

import librosa
import numpy as np
import os
import soundcard as sc
import threading
from cv2.typing import MatLike
from enum import Enum
from scipy.signal import correlate
from sklearn.preprocessing import scale
from typing import Optional, List, Union

from one_dragon.base.conditional_operation.state_event import StateEvent
from one_dragon.utils import cal_utils
from one_dragon.utils import thread_utils, os_utils
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.yolo.dodge_classifier import DodgeClassifier

_dodge_check_executor = ThreadPoolExecutor(thread_name_prefix='od_yolo_check', max_workers=16)


class AudioRecorder:

    def __init__(self):
        self.running: bool = False
        self._run_lock = threading.Lock()

        self._sample_rate = 32000  # 采样率
        self._used_channel = 2
        self._mic = sc.default_microphone()

        self.latest_audio = np.zeros(self._sample_rate)  # 1秒的音频帧数

    def start_running_async(self, interval: float = 0.01) -> None:
        with self._run_lock:
            if self.running:
                return

            self.running = True

        self.latest_audio = np.zeros(self._sample_rate)
        future = _dodge_check_executor.submit(self._record_loop, interval)
        future.add_done_callback(thread_utils.handle_future_result)

    def _record_loop(self, interval: float = 0.01) -> None:
        window_size = int(self._sample_rate * interval)
        while self.running:
            recording = self._mic.record(numframes=window_size, samplerate=self._sample_rate, channels=self._used_channel)
            mono = librosa.to_mono(recording)
            latest_audio = np.roll(self.latest_audio, -len(mono))
            latest_audio[-len(mono):] = mono
            self.latest_audio = latest_audio

    def stop_running(self) -> None:
        self.running = False


class YoloStateEventEnum(Enum):

    DODGE_YELLOW = '闪避识别-黄光'
    DODGE_RED = '闪避识别-红光'
    DODGE_AUDIO = '闪避识别-声音'


class BattleDodgeContext:

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        self._flash_model: Optional[DodgeClassifier] = None
        self._audio_recorder: AudioRecorder = AudioRecorder()
        self._audio_template: Optional[np.ndarray] = None

        # 识别锁 保证每种类型只有1实例在进行识别
        self._check_dodge_flash_lock = threading.Lock()
        self._check_audio_lock = threading.Lock()

        # 识别间隔
        self._check_dodge_interval: Union[float, List[float]] = 0
        self._check_audio_interval: float = 0.02

        # 上一次识别的时间
        self._last_check_dodge_time: float = 0
        self._last_check_audio_time: float = 0

    def init_context(self,
                     use_gpu: bool = True,
                     check_dodge_interval: Union[float, List[float]] = 0,
                     audio_recorder_interval: float = 0.01,
                     check_audio_interval: float = 0.02
                     ) -> None:
        """
        运行前 初始化上下文
        :return:
        """
        if self._flash_model is None or self._flash_model.gpu != use_gpu:
            self._flash_model = DodgeClassifier(
                model_parent_dir_path=os_utils.get_path_under_work_dir('assets', 'models', 'yolo'),
                gpu=use_gpu
            )

        # 识别间隔
        self._check_dodge_interval = check_dodge_interval
        self._check_audio_interval = check_audio_interval

        # 上一次识别的时间
        self._last_check_dodge_time = 0
        self._last_check_audio_time = 0

        self._audio_recorder.start_running_async(audio_recorder_interval)

        # 异步加载音频 这个比较慢
        _dodge_check_executor.submit(self.init_audio_template)

    def init_audio_template(self) -> None:
        """
        加载音频模板
        :return:
        """
        if self._audio_template is not None:
            return
        log.info('加载声音模板中')
        self._audio_template, _ = librosa.load(os.path.join(
            os_utils.get_path_under_work_dir('assets', 'template', 'dodge_audio'),
            'template_1.wav'
        ), sr=32000)
        log.info('加载声音模板完成')

    def check_screen(self, screen: MatLike, screenshot_time: float, sync: bool = False) -> None:
        """
        异步识别画面
        :return:
        """
        future_list: List[Future] = []
        audio_future = _dodge_check_executor.submit(self.check_dodge_audio, screen, screenshot_time)
        future_list.append(audio_future)
        future_list.append(_dodge_check_executor.submit(self.check_dodge_flash, screen, screenshot_time, audio_future))

        for future in future_list:
            future.add_done_callback(thread_utils.handle_future_result)

        if sync:
            for future in future_list:
                future.result()

    def check_dodge_flash(self, screen: MatLike, screenshot_time: float, audio_future: Optional[Future[bool]] = None) -> bool:
        """
        识别画面是否有闪光
        :param screen:
        :param screenshot_time:
        :return:
        """
        if not self._check_dodge_flash_lock.acquire(blocking=False):
            return False

        try:
            if screenshot_time - self._last_check_dodge_time < cal_utils.random_in_range(self._check_dodge_interval):
                # 还没有达到识别间隔
                return False

            self._last_check_dodge_time = screenshot_time

            result = self._flash_model.run(screen)
            with_flash: bool = False
            if result.class_idx == 1:
                e = YoloStateEventEnum.DODGE_RED.value
                self.ctx.dispatch_event(e, StateEvent(screenshot_time))
                with_flash = True
            elif result.class_idx == 2:
                e = YoloStateEventEnum.DODGE_YELLOW.value
                self.ctx.dispatch_event(e, StateEvent(screenshot_time))
                with_flash = True
            elif audio_future is not None:
                audio_result = audio_future.result()
                if audio_result:
                    e = YoloStateEventEnum.DODGE_AUDIO.value
                    self.ctx.dispatch_event(e, StateEvent(screenshot_time))
                    with_flash = True

            return with_flash
        except Exception:
            log.error('识别画面闪光失败', exc_info=True)
        finally:
            self._check_dodge_flash_lock.release()

    def check_dodge_audio(self, screenshot_time: float) -> bool:
        if not self._check_audio_lock.acquire(blocking=False):
            return False

        try:
            if screenshot_time - self._last_check_audio_time < cal_utils.random_in_range(self._check_audio_interval):
                # 还没有达到识别间隔
                return False
            if self._audio_template is None:
                return False
            self._last_check_audio_time = screenshot_time

            corr = self.get_max_corr(self._audio_template, self._audio_recorder.latest_audio)

            return corr > 0.1
        except Exception:
            log.error('识别画面闪光失败', exc_info=True)
        finally:
            self._check_dodge_flash_lock.release()

    @staticmethod
    def get_max_corr(x: np.ndarray, y: np.ndarray):
        # 标准化
        wx = scale(x, with_mean=False)
        wy = scale(y, with_mean=False)

        # 计算NCC
        if wx.shape[0] > wy.shape[0]:
            correlation = correlate(wx, wy, mode='same', method='fft') / wx.shape[0]
        else:
            correlation = correlate(wy, wx, mode='same', method='fft') / wy.shape[0]

        max_corr = np.max(correlation)

        return max_corr


def __debug():
    ctx = ZContext()
    ctx.init_by_config()

    from one_dragon.utils import debug_utils
    img = debug_utils.get_debug_image('flash')

    ctx.yolo.init_context(use_gpu=False)
    result = ctx.yolo._dodge_model.run(img)


if __name__ == '__main__':
    __debug()