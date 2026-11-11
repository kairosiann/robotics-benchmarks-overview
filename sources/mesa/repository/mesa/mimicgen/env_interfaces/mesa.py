import numpy as np
import robosuite.utils.transform_utils as T

import mesa.mimicgen.utils.pose_utils as PoseUtils
from mesa.mimicgen.env_interfaces.robosuite import RobosuiteInterface


class MESAInterface(RobosuiteInterface):
    """
    A general MimicGen environment interface for MESA tasks.
    """

    INTERFACE_TYPE = "mesa"
    
    def __init__(self, env):
        super().__init__(env)
        self.parsed_problem = env.parsed_problem

    @staticmethod
    def _get_term_signal_key_from_demo_state(demo_state, prefix=None, suffix=None):
        key = "_".join(demo_state)
        if prefix:
            key = f"{prefix}_{key}"
        if suffix:
            key = f"{key}_{suffix}"
        return key

    def get_object_poses(self):
        """
        Returns poses of objects and fixtures in the environment.
        Currently does not include site objects.
        """
        object_poses = dict()
        for obj_name in self.env.objects_dict:
            obj_id = self.env.obj_body_id[obj_name]
            obj_pos = np.array(self.env.sim.data.body_xpos[obj_id])
            obj_rot = np.array(self.env.sim.data.body_xmat[obj_id].reshape(3, 3))
            object_poses[obj_name] = PoseUtils.make_pose(obj_pos, obj_rot)
        for obj_name in self.env.fixtures_dict:
            obj_id = self.env.obj_body_id[obj_name]
            obj_pos = np.array(self.env.sim.data.body_xpos[obj_id])
            obj_rot = np.array(self.env.sim.data.body_xmat[obj_id].reshape(3, 3))
            object_poses[obj_name] = PoseUtils.make_pose(obj_pos, obj_rot)
        
        for demonstration_state in self.parsed_problem["demonstration_states"]:
            target = demonstration_state[-1]
            geom_state = self.env.object_states_dict[target].get_geom_state()
            obj_pos = geom_state["pos"]
            obj_rot_quat = geom_state["quat"]
            obj_rot_mat = T.quat2mat(obj_rot_quat)
            object_poses[target] = PoseUtils.make_pose(obj_pos, obj_rot_mat)
        return object_poses

    def get_subtask_term_signals(self):
        # Using partial metrics checks for all provided predicates
        signals = dict()
        subtask_predicates = self.env.parsed_problem["demonstration_states"]
        for i, subtask_predicate in enumerate(subtask_predicates):
            subtask_id = f"subtask_{i+1}"
            signals[subtask_id] = int(self.env._eval_predicate(subtask_predicate))
        return signals
