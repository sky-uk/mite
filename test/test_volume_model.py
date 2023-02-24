from pytest import raises

from mite.scenario import StopVolumeModel
from mite.volume_model import Constant, Nothing, Ramp


class TestNothing:
    def test_nothing(self):
        vm = Nothing(duration=60)
        assert vm(1, 2) == 0

    def test_nothing_raises_stop(self):
        vm = Nothing(duration=60)
        assert vm(60, 61) == 0
        with raises(StopVolumeModel):
            vm(61, 62)


class TestConstant:
    def test_constant(self):
        vm = Constant(duration=60, tps=1)
        assert vm(1, 2) == 1

    def test_constant_raises_stop(self):
        vm = Constant(duration=60, tps=1)
        assert vm(60, 61) == 1
        with raises(StopVolumeModel):
            vm(61, 62)


class TestCompound:
    def test_simple_compound(self):
        vm = Nothing(10) + Constant(duration=10, tps=1)
        assert vm(1, 2) == 0
        assert vm(10, 11) == 1
        with raises(StopVolumeModel):
            vm(21, 22)

    def test_addition_to_other_type_raises(self):
        with raises(ValueError):
            Nothing(10) + 2


class TestRamp:
    def test_simple_ramp(self):
        vm = Nothing(10) + Ramp(10) + Constant(tps=2, duration=10)
        assert vm(1, 2) == 0
        assert vm(10, 11) == 0
        assert vm(15, 16) == 1
        assert vm(20, 21) == 2
        with raises(StopVolumeModel):
            vm(31, 32)

    def test_ramp_to_zero(self):
        vm = Constant(tps=2, duration=10) + Ramp(duration=10, to=0)
        assert vm(1, 2) == 2
        assert vm(10, 11) == 2
        assert vm(15, 16) == 1
        assert vm(20, 21) == 0
        with raises(StopVolumeModel):
            vm(21, 22)

    def test_ramp_from_zero(self):
        vm = Ramp(duration=10, frm=0) + Constant(tps=2, duration=10)
        assert vm(1, 2) == 0
        assert vm(5, 6) == 1
        assert vm(10, 11) == 2
        assert vm(20, 21) == 2
        with raises(StopVolumeModel):
            vm(21, 22)

    def test_final_ramp_without_to_raises(self):
        vm = Constant(tps=2, duration=10) + Ramp(duration=10)
        with raises(Exception, match="^You must specify 'to'.*"):
            vm(1, 2)

    def test_initial_ramp_without_frm_raises(self):
        vm = Ramp(duration=10) + Constant(tps=2, duration=10)
        with raises(Exception, match="^You must specify 'frm'.*"):
            vm(1, 2)

    def test_ramp_inside_chain_with_to_raises(self):
        vm = (
            Constant(tps=1, duration=10)
            + Ramp(duration=10, to=0)
            + Constant(tps=1, duration=10)
        )
        with raises(Exception, match="^A ramp with 'to' specified must.*"):
            vm(1, 2)

    def test_ramp_inside_chain_with_frm_raises(self):
        vm = (
            Constant(tps=1, duration=10)
            + Ramp(duration=10, frm=0)
            + Constant(tps=1, duration=10)
        )
        with raises(Exception, match="^A ramp with 'frm' specified must.*"):
            vm(1, 2)

    def test_ramp_alone_raises(self):
        vm = Ramp(10)
        with raises(Exception, match="^Ramp was called outside of.*"):
            vm(1, 2)

    def test_addition_when_rhs_is_compound(self):
        vm = Nothing(10) + (Ramp(10) + Constant(tps=2, duration=10))
        assert vm(1, 2) == 0
        assert vm(10, 11) == 0
        assert vm(15, 16) == 1
        assert vm(20, 21) == 2
        with raises(StopVolumeModel):
            vm(31, 32)
