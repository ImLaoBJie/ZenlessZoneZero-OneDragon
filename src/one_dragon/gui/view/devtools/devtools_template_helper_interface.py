import os
from PySide6.QtWidgets import QWidget, QFileDialog, QTableWidgetItem
from cv2.typing import MatLike
from qfluentwidgets import FluentIcon, PushButton, TableWidget, ToolButton, ComboBox, ImageLabel, CaptionLabel
from typing import List, Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.screen.template_info import TemplateInfo, TemplateShapeEnum
from one_dragon.gui.component.column_widget import ColumnWidget
from one_dragon.gui.component.cv2_image import Cv2Image
from one_dragon.gui.component.interface.vertical_scroll_interface import VerticalScrollInterface
from one_dragon.gui.component.label.click_image_label import ClickImageLabel, ImageScaleEnum
from one_dragon.gui.component.row_widget import RowWidget
from one_dragon.gui.component.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon.gui.component.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon.gui.component.setting_card.text_setting_card import TextSettingCard
from one_dragon.utils import os_utils, cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class DevtoolsTemplateHelperInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonContext, parent=None):
        content_widget = RowWidget()

        content_widget.add_widget(self._init_left_part())
        content_widget.add_widget(self._init_mid_part())
        content_widget.add_widget(self._init_right_part())

        self.chosen_template: Optional[TemplateInfo] = None

        VerticalScrollInterface.__init__(
            self,
            ctx=ctx,
            object_name='devtools_template_helper_interface',
            parent=parent,
            content_widget=content_widget,
            nav_text_cn='模板管理'
        )

    def _init_left_part(self) -> QWidget:
        widget = ColumnWidget()

        btn_row = RowWidget()
        widget.add_widget(btn_row)

        self.existed_yml_btn = ComboBox()
        self.existed_yml_btn.setPlaceholderText(gt('选择已有', 'ui'))
        btn_row.add_widget(self.existed_yml_btn)

        self.create_btn = PushButton(text=gt('新建', 'ui'))
        self.create_btn.clicked.connect(self._on_create_clicked)
        btn_row.add_widget(self.create_btn)

        self.copy_btn = PushButton(text=gt('复制', 'ui'))
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        btn_row.add_widget(self.copy_btn)

        self.delete_btn = PushButton(text=gt('删除', 'ui'))
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        btn_row.add_widget(self.delete_btn)

        self.cancel_btn = PushButton(text=gt('取消', 'ui'))
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.add_widget(self.cancel_btn)

        btn_row.add_stretch(1)

        save_row = RowWidget()
        widget.add_widget(save_row)

        self.save_config_btn = PushButton(text=gt('保存配置', 'ui'))
        self.save_config_btn.clicked.connect(self._on_save_config_clicked)
        save_row.add_widget(self.save_config_btn)

        self.save_raw_btn = PushButton(text=gt('保存模板', 'ui'))
        self.save_raw_btn.clicked.connect(self._on_save_raw_clicked)
        save_row.add_widget(self.save_raw_btn)

        self.save_mask_btn = PushButton(text=gt('保存掩码', 'ui'))
        self.save_mask_btn.clicked.connect(self._on_save_mask_clicked)
        save_row.add_widget(self.save_mask_btn)

        save_row.add_stretch(1)

        self.choose_image_btn = PushButton(text=gt('选择图片', 'ui'))
        self.choose_image_btn.clicked.connect(self.choose_existed_image)
        widget.add_widget(self.choose_image_btn)

        self.template_sub_dir_opt = TextSettingCard(icon=FluentIcon.HOME, title='画面')
        self.template_sub_dir_opt.line_edit.setFixedWidth(240)
        self.template_sub_dir_opt.value_changed.connect(self._on_template_sub_dir_changed)
        widget.add_widget(self.template_sub_dir_opt)

        self.template_id_opt = TextSettingCard(icon=FluentIcon.HOME, title='模板ID')
        self.template_id_opt.line_edit.setFixedWidth(240)
        self.template_id_opt.value_changed.connect(self._on_template_id_changed)
        widget.add_widget(self.template_id_opt)

        self.template_name_opt = TextSettingCard(icon=FluentIcon.HOME, title='模板名称')
        self.template_name_opt.line_edit.setFixedWidth(240)
        self.template_name_opt.value_changed.connect(self._on_template_name_changed)
        widget.add_widget(self.template_name_opt)

        self.template_shape_opt = ComboBoxSettingCard(icon=FluentIcon.FIT_PAGE, title='形状', options_enum=TemplateShapeEnum)
        self.template_shape_opt.value_changed.connect(self._on_template_shape_changed)
        widget.add_widget(self.template_shape_opt)

        self.auto_mask_opt = SwitchSettingCard(icon=FluentIcon.HOME, title='自动生成掩码')
        self.auto_mask_opt.value_changed.connect(self._on_auto_mask_changed)
        widget.add_widget(self.auto_mask_opt)

        self.point_table = TableWidget()
        self.point_table.setMinimumWidth(300)
        self.point_table.setMinimumHeight(220)
        self.point_table.setBorderVisible(True)
        self.point_table.setBorderRadius(8)
        self.point_table.setWordWrap(True)
        self.point_table.setColumnCount(2)
        self.point_table.verticalHeader().hide()
        self.point_table.setHorizontalHeaderLabels([
            gt('操作', 'ui'),
            gt('点位', 'ui'),
        ])
        self.point_table.setColumnWidth(0, 40)  # 操作
        self.point_table.setColumnWidth(1, 200)  # 位置
        widget.add_widget(self.point_table)

        widget.add_stretch(1)
        return widget

    def _init_mid_part(self) -> QWidget:
        widget = ColumnWidget()

        raw_label = CaptionLabel(text='模板原图')
        widget.add_widget(raw_label)

        self.template_raw_label = ImageLabel()
        widget.add_widget(self.template_raw_label)

        mask_label = CaptionLabel(text='模板掩码')
        widget.add_widget(mask_label)

        self.template_mask_label = ImageLabel()
        widget.add_widget(self.template_mask_label)

        merge_label = CaptionLabel(text='模板抠图')
        widget.add_widget(merge_label)

        self.template_merge_label = ImageLabel()
        widget.add_widget(self.template_merge_label)

        widget.add_stretch(1)

        return widget

    def _init_right_part(self) -> QWidget:
        widget = ColumnWidget()

        self.image_display_size_opt = ComboBoxSettingCard(
            icon=FluentIcon.ZOOM_IN, title='图片显示大小',
            options_enum=ImageScaleEnum
        )
        self.image_display_size_opt.setValue(0.5)
        self.image_display_size_opt.value_changed.connect(self._update_screen_image_display)
        widget.add_widget(self.image_display_size_opt)

        self.image_click_pos_opt = TextSettingCard(icon=FluentIcon.MOVE, title='鼠标选择区域')
        widget.add_widget(self.image_click_pos_opt)

        self.image_label = ClickImageLabel()
        self.image_label.clicked_with_pos.connect(self._on_image_clicked)
        widget.add_widget(self.image_label)

        widget.add_stretch(1)

        return widget

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self._update_whole_display()

    def _update_whole_display(self) -> None:
        """
        根据画面图片，统一更新界面的显示
        :return:
        """
        chosen = self.chosen_template is not None

        self.existed_yml_btn.setDisabled(chosen)
        self.create_btn.setDisabled(chosen)
        self.copy_btn.setDisabled(not chosen)
        self.delete_btn.setDisabled(not chosen)
        self.cancel_btn.setDisabled(not chosen)

        self.save_config_btn.setDisabled(not chosen)
        self.save_raw_btn.setDisabled(not chosen)
        self.save_mask_btn.setDisabled(not chosen)

        self.choose_image_btn.setDisabled(not chosen)
        self.template_sub_dir_opt.setDisabled(not chosen)
        self.template_id_opt.setDisabled(not chosen)
        self.template_name_opt.setDisabled(not chosen)
        self.template_shape_opt.setDisabled(not chosen)
        self.auto_mask_opt.setDisabled(not chosen)

        if not chosen:  # 清除一些值
            self.template_sub_dir_opt.setValue('')
            self.template_id_opt.setValue('')
            self.template_name_opt.setValue('')
            self.template_shape_opt.setValue('')
            self.auto_mask_opt.setValue(True)
        else:
            self.template_sub_dir_opt.setValue(self.chosen_template.sub_dir)
            self.template_id_opt.setValue(self.chosen_template.template_id)
            self.template_name_opt.setValue(self.chosen_template.template_name)
            self.template_shape_opt.setValue(self.chosen_template.template_shape)
            self.auto_mask_opt.setValue(self.chosen_template.auto_mask)

        self._update_existed_yml_options()
        self._update_all_image_display()
        self._update_point_table_display()

    def _update_existed_yml_options(self) -> None:
        """
        更新已有的yml选项
        :return:
        """
        try:
            # 更新之前 先取消原来的监听 防止触发事件
            self.existed_yml_btn.currentIndexChanged.disconnect(self._on_choose_existed_yml)
        except Exception:
            pass
        self.existed_yml_btn.clear()
        template_info_list: List[TemplateInfo] = self.ctx.template_loader.get_all_template_info_from_disk(need_raw=False, need_config=True)
        for template_info in template_info_list:
            self.existed_yml_btn.addItem(text=template_info.template_name, icon=None, userData=template_info)
        self.existed_yml_btn.setCurrentIndex(-1)
        self.existed_yml_btn.setPlaceholderText(gt('选择已有', 'ui'))
        self.existed_yml_btn.currentIndexChanged.connect(self._on_choose_existed_yml)

    def _update_point_table_display(self):
        """
        更新区域表格的显示
        :return:
        """
        try:
            # 更新之前 先取消原来的监听 防止触发事件
            self.point_table.cellChanged.disconnect(self._on_point_table_cell_changed)
        except Exception:
            pass
        point_list: List[Point] = [] if self.chosen_template is None else self.chosen_template.point_list
        point_cnt = len(point_list)
        self.point_table.setRowCount(point_cnt + 1)

        for idx in range(point_cnt):
            point_item = point_list[idx]
            del_btn = ToolButton(FluentIcon.DELETE, parent=None)
            del_btn.clicked.connect(self._on_row_delete_clicked)

            self.point_table.setCellWidget(idx, 0, del_btn)
            self.point_table.setItem(idx, 1, QTableWidgetItem('%d, %d' % (point_item.x, point_item.y)))

        self.point_table.cellChanged.connect(self._on_point_table_cell_changed)

    def _update_all_image_display(self) -> None:
        """
        更新所有图片的显示
        :return:
        """
        self._update_screen_image_display()
        self._update_template_raw_display()
        self._update_template_mask_display()
        self._update_template_merge_display()

    def _update_screen_image_display(self):
        """
        更新游戏画面图片的显示
        :return:
        """
        image_to_show = self.chosen_template.get_screen_image_to_display() if self.chosen_template is not None else None

        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            self.image_label.setImage(image)
            size_value: float = self.image_display_size_opt.getValue()
            if size_value is None:
                display_width = image.width()
                display_height = image.height()
            else:
                display_width = int(image.width() * size_value)
                display_height = int(image.height() * size_value)
            self.image_label.setFixedSize(display_width, display_height)
        else:
            self.image_label.setImage(None)

    def _update_template_raw_display(self) -> None:
        """
        更新模板原图的显示
        :return:
        """
        image_to_show = self.chosen_template.get_template_raw_to_display() if self.chosen_template is not None else None
        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            self.template_raw_label.setImage(image)
            self.template_raw_label.setFixedSize(image.width(), image.height())
        else:
            self.template_raw_label.setImage(None)

    def _update_template_mask_display(self) -> None:
        """
        更新模板掩码的显示
        :return:
        """
        image_to_show = self.chosen_template.get_template_mask_to_display() if self.chosen_template is not None else None

        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            self.template_mask_label.setImage(image)
            self.template_mask_label.setFixedSize(image.width(), image.height())
        else:
            self.template_mask_label.setImage(None)

    def _update_template_merge_display(self) -> None:
        """
        更新模板抠图的显示
        :return:
        """
        image_to_show = self.chosen_template.get_template_merge_to_display() if self.chosen_template is not None else None

        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            self.template_merge_label.setImage(image)
            self.template_merge_label.setFixedSize(image.width(), image.height())
        else:
            self.template_merge_label.setImage(None)

    def _on_choose_existed_yml(self, idx: int):
        """
        选择了已有的yml
        :param idx:
        :return:
        """
        self.chosen_template: TemplateInfo = self.existed_yml_btn.items[idx].userData
        self._update_whole_display()

    def _on_create_clicked(self):
        """
        创建一个新的
        :return:
        """
        if self.chosen_template is not None:
            return

        self.chosen_template = TemplateInfo('', '')
        self._update_whole_display()

    def _on_copy_clicked(self):
        """
        复制一个
        :return:
        """
        if self.chosen_template is None:
            return

        self.chosen_template.copy_new()
        self._update_whole_display()

    def _on_save_config_clicked(self) -> None:
        """
        保存配置
        :return:
        """
        if self.chosen_template is None:
            return

        self.chosen_template.save_config()
        self._update_existed_yml_options()

    def _on_save_raw_clicked(self) -> None:
        """
        保存配置
        :return:
        """
        if self.chosen_template is None:
            return

        self.chosen_template.save_raw()
        self._update_existed_yml_options()

    def _on_save_mask_clicked(self) -> None:
        """
        保存掩码
        :return:
        """
        if self.chosen_template is None:
            return

        self.chosen_template.save_mask()
        self._update_existed_yml_options()

    def _on_delete_clicked(self) -> None:
        """
        删除
        :return:
        """
        if self.chosen_template is None:
            return
        self.chosen_template.delete()
        self.chosen_template = None
        self._update_whole_display()

    def _on_cancel_clicked(self) -> None:
        """
        取消编辑
        :return:
        """
        if self.chosen_template is None:
            return
        self.chosen_template = None
        self.existed_yml_btn.setCurrentIndex(-1)
        self._update_whole_display()

    def choose_existed_image(self) -> None:
        """
        选择已有的环图片
        :return:
        """
        default_dir = os_utils.get_path_under_work_dir('.debug', 'images')
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            gt('选择图片', 'ui'),
            dir=default_dir,
            filter="PNG (*.png)",
        )
        if file_path is not None and file_path.endswith('.png'):
            fix_file_path = os.path.normpath(file_path)
            log.info('选择路径 %s', fix_file_path)
            self._on_image_chosen(fix_file_path)

    def _on_image_chosen(self, image_file_path: str) -> None:
        """
        选择图片之后的回调
        :param image_file_path:
        :return:
        """
        if self.chosen_template is None:
            return

        self.chosen_template.screen_image = cv2_utils.read_image(image_file_path)
        self._update_all_image_display()

    def _on_template_sub_dir_changed(self, value: str) -> None:
        if self.chosen_template is None:
            return

        self.chosen_template.sub_dir = value

    def _on_template_id_changed(self, value: str) -> None:
        if self.chosen_template is None:
            return

        self.chosen_template.template_id = value

    def _on_template_name_changed(self, value: str) -> None:
        if self.chosen_template is None:
            return

        self.chosen_template.template_name = value

    def _on_template_shape_changed(self, idx: int, value: str) -> None:
        if self.chosen_template is None:
            return

        self.chosen_template.update_template_shape(value)
        self._update_point_table_display()
        self._update_all_image_display()

    def _on_auto_mask_changed(self, value: bool) -> None:
        if self.chosen_template is None:
            return

        self.chosen_template.auto_mask = value
        self._update_all_image_display()

    def _on_row_delete_clicked(self):
        """
        删除一行
        :return:
        """
        if self.chosen_template is None:
            return

        button_idx = self.sender()
        if button_idx is not None:
            row_idx = self.point_table.indexAt(button_idx.pos()).row()
            self.chosen_template.remove_point_by_idx(row_idx)
            self.point_table.removeRow(row_idx)
            self._update_all_image_display()

    def _on_point_table_cell_changed(self, row: int, column: int) -> None:
        """
        表格内容改变
        :param row:
        :param column:
        :return:
        """
        if self.chosen_template is None:
            return
        if row < 0 or row >= len(self.chosen_template.point_list):
            return
        text = self.point_table.item(row, column).text().strip()
        if column == 1:
            num_list = [int(i) for i in text.split(',')]
            self.chosen_template.point_list[row] = Point(num_list[0], num_list[1])
            self.chosen_template.point_updated = True
            self._update_all_image_display()

    def _on_image_clicked(self, x1: int, y1: int) -> None:
        """
        图片上拖拽区域后 显示坐标
        :return:
        """
        if self.chosen_template is None or self.chosen_template.screen_image is None:
            return
        display_width = self.image_label.width()
        display_height = self.image_label.height()

        image_width = self.chosen_template.screen_image.shape[1]
        image_height = self.chosen_template.screen_image.shape[0]

        real_x = int(x1 * image_width / display_width)
        real_y = int(y1 * image_height / display_height)

        self.chosen_template.add_point(Point(real_x, real_y))

        self._update_point_table_display()
        self._update_all_image_display()
