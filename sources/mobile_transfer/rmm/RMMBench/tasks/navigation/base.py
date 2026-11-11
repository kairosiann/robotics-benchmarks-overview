from RMMBench.tasks.dm_task import LM4ManipBaseTask
from RMMBench.tasks.condition import ConditionSet, AsynSequenceCondition
from RMMBench.utils.register import register
import copy


class CompositeNavigationTask(LM4ManipBaseTask):
    """
    Base class for composite navigation tasks with multiple target areas.
    Supports ordered navigation using AsynSequenceCondition.

    Example condition config for sequential navigation:
        conditions_config = dict(
            asyn_sequence=[
                # Step 0: Navigate to first area
                dict(
                    contain_robot_pose=dict(
                        target_bbox=bbox_0,
                        robot="pandaomron"
                    )
                ),
                # Step 1: Navigate to second area
                dict(
                    contain_robot_pose=dict(
                        target_bbox=bbox_1,
                        robot="pandaomron"
                    )
                )
            ]
        )
    """

    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)

    def init_conditions(self):
        """
        Initialize conditions for composite navigation task.
        Supports 'asyn_sequence' condition for ordered navigation to multiple areas.
        Each step in the sequence can contain multiple conditions (AND logic within step).
        """
        # print("self.entities = ", self.entities)
        # exit()
        if self.config["task"].get("conditions", None) is not None:
            condition_config = copy.deepcopy(self.config["task"]["conditions"])
        else:
            self.conditions = None
            return False

        # Handle simple conditions (non-sequence) - fallback to base class
        if "asyn_sequence" not in condition_config.keys():
            return super().init_conditions()

        # Handle asyn_sequence condition for composite navigation
        condition_sets = []
        for step_config in condition_config["asyn_sequence"]:
            # Each step is a dict of conditions that must ALL be met (AND logic)
            step_conditions = []
            for condition_key, specific_condition in step_config.items():
                # print("condition_key:", condition_key)

                # print("specific_condition:", specific_condition)
                condition_cls = register.load_condition(condition_key)

                # Parse entities: convert string names to entity objects
                for k, entities in specific_condition.items():
                    # print("entities:", entities)
                    # print("k:", k)
                    if k in ["robot"]:
                        specific_condition[k] = self.robot
                        continue
                    if k in ["container_name","target_bbox", "positions", "target_pos_range","target_orientation","joint_name"]:
                        # Keep these values as-is (data, not entity names)
                        continue
                    if isinstance(entities, str):
                        specific_condition[k] = self.entities.get(entities, None)
                    elif isinstance(entities, list):

                        # Check if list contains entity names (strings) or data
                        if entities and isinstance(entities[0], str):
                            specific_condition[k] = [self.entities.get(entity, None) for entity in entities]

                condition = condition_cls(**specific_condition)
                step_conditions.append(condition)

                # Track navigation condition for each step
                if condition_key in ["contain_robot_pose"]:
                    self.navigation_condition = condition
                    # print("@@@@@@@@condition:",condition)

            # Wrap step conditions in ConditionSet (AND logic within each step)
            # print("step_conditions:", step_conditions)
            condition_set = ConditionSet(step_conditions)
            condition_sets.append(condition_set)

        # Read the ordered constraints (optional) and pass them to AsynSequenceCondition
        ordered_indices = condition_config.get("ordered_indices", None)

        # Create AsynSequenceCondition: steps must be completed in order
        self.conditions = AsynSequenceCondition(condition_sets, ordered_indices=ordered_indices)
        return True
