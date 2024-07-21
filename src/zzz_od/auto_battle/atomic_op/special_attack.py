from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from zzz_od.context.battle_context import BattleEventEnum
from zzz_od.context.zzz_context import ZContext


class AtomicSpecialAttack(AtomicOp):

    def __init__(self, ctx: ZContext):
        AtomicOp.__init__(self, op_name=BattleEventEnum.BTN_SWITCH_SPECIAL_ATTACK.value)
        self.ctx: ZContext = ctx

    def execute(self):
        self.ctx.special_attack()