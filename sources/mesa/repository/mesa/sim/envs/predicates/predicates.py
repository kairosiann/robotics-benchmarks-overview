from mesa.sim.envs.constants import LIFT_HEIGHT_THRESHOLD


class Expression:
    def __init__(self):
        raise NotImplementedError

    def __call__(self):
        raise NotImplementedError


class UnaryAtomic(Expression):
    def __init__(self):
        pass

    def __call__(self, arg1):
        raise NotImplementedError


class BinaryAtomic(Expression):
    def __init__(self):
        pass

    def __call__(self, arg1, arg2):
        raise NotImplementedError


class MultiarayAtomic(Expression):
    def __init__(self):
        pass

    def __call__(self, *args):
        raise NotImplementedError


class TruePredicateFn(MultiarayAtomic):
    def __init__(self):
        super().__init__()

    def __call__(self, *args):
        return True


class FalsePredicateFn(MultiarayAtomic):
    def __init__(self):
        super().__init__()

    def __call__(self, *args):
        return False


class InContactPredicateFn(BinaryAtomic):
    def __call__(self, arg1, arg2):
        return arg1.check_contact(arg2)


class In(BinaryAtomic):
    def __call__(self, arg1, arg2):
        return arg2.check_contact(arg1) and arg2.check_contain(arg1)


class On(BinaryAtomic):
    def __call__(self, arg1, arg2):
        return arg2.check_ontop(arg1)


class Up(BinaryAtomic):
    def __call__(self, arg1):
        return arg1.get_geom_state()["pos"][2] >= LIFT_HEIGHT_THRESHOLD


class PrintJointState(UnaryAtomic):
    """This is a debug predicate to allow you print the joint values of the object you care"""

    def __call__(self, arg):
        print(arg.get_joint_state())
        return True


class Open(UnaryAtomic):
    def __call__(self, arg):
        return arg.is_open()


class Close(UnaryAtomic):
    def __call__(self, arg):
        return arg.is_close()


class TurnOn(UnaryAtomic):
    def __call__(self, arg):
        return arg.turn_on()


class TurnOff(UnaryAtomic):
    def __call__(self, arg):
        return arg.turn_off()


class Grasp(UnaryAtomic):
    def __call__(self, arg1):
        return arg1.check_grasp()


class GraspLeft(UnaryAtomic):
    def __call__(self, arg1):
        return arg1.check_grasp(robot_index=0)


class GraspRight(UnaryAtomic):
    def __call__(self, arg1):
        return arg1.check_grasp(robot_index=1)


class Lifted(UnaryAtomic):
    def __call__(self, arg1):
        return arg1.get_geom_state()["pos"][2] >= LIFT_HEIGHT_THRESHOLD


class Stack(BinaryAtomic):
    def __call__(self, arg1, arg2):
        if not arg1.check_ontop(arg2):
            return False
        pos1 = arg1.get_geom_state()["pos"]
        pos2 = arg2.get_geom_state()["pos"]
        if arg1.stack_info:
            xy_threshold = arg1.stack_info["xy_threshold"]
            z_threshold = arg1.stack_info["z_threshold"]
        elif arg2.stack_info:
            xy_threshold = arg2.stack_info["xy_threshold"]
            z_threshold = arg2.stack_info["z_threshold"]
        else:
            xy_threshold = 0.03
            z_threshold = 0.07
        xy_close = (abs(pos1[0] - pos2[0]) < xy_threshold) and (abs(pos1[1] - pos2[1]) < xy_threshold)
        z_close = abs(pos1[2] - pos2[2]) < z_threshold
        return xy_close and z_close