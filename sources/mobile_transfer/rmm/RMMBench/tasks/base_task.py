import copy

from RMMBench.tasks.dm_task import *
from RMMBench.tasks.condition import ConditionSet, OrCondition, AsynSequenceCondition


class PrimitiveTask(LM4ManipBaseTask):
    """
    Base PrimitiveTask, migrated from primitive/base.py.
    Base class for all Primitive-type tasks.
    """

    def reset_intention_distance(self):
        self.intention_distance = dict()
        entity_names = list(self.entities.keys())
        for ignore_entity in self.random_ignored_entities:
            if ignore_entity in entity_names:
                entity_names.remove(ignore_entity)
        for entity_name in entity_names:
            self.intention_distance[entity_name] = np.inf

    def reset_task_progress(self):
        self.target_is_grasped = dict()
        if isinstance(self.target_entity, str):
            self.target_is_grasped[self.target_entity] = False
        elif isinstance(self.target_entity, list):
            for entity in self.target_entity:
                self.target_is_grasped[entity] = False

    def extract_base_name(self, name):
        match = re.match(r'([a-zA-Z]+)', name)
        return match.group(1) if match else name

    def update_intention_distance(self, physics):
        ee_pos = self.robot.get_end_effector_pos(physics)
        for key, entity in self.entities.items():
            if key in self.random_ignored_entities:
                continue
            self.intention_distance[key] = min(self.intention_distance[key], distance(ee_pos, entity.get_xpos(physics)))

    def update_task_progress(self, physics):
        if isinstance(self.target_entity, list):
            for entity in self.target_entity:
                if self.entities[entity].is_grasped(physics, self.robot):
                    self.target_is_grasped[entity] = True
        elif isinstance(self.target_entity, str):
            if self.entities[self.target_entity].is_grasped(physics, self.robot):
                self.target_is_grasped[self.target_entity] = True

    def get_intention_score(self, physics, threshold=0.2, discrete=True):
        if isinstance(self.target_entity, list):
            return self.get_intention_score_to_entity(physics, self.target_entity[-1], threshold, discrete)
        return self.get_intention_score_to_entity(physics, self.target_entity, threshold, discrete)

    def get_task_progress(self, physics):
        # FIXME: temporary solution: in primitive tasks, a successful pick often occupies half of the task progress
        _, conditions_met = self.conditions.met_progress(physics)
        n_condition = len(self.conditions)
        n_condition += len(self.target_is_grasped)
        target_entity_met = []
        for value in self.target_is_grasped.values():
            if value:
                target_entity_met.append(value)
        return (len(conditions_met) + len(target_entity_met)) / n_condition

    def get_intention_score_to_entity(self, physics, entity_name, threshold=0.2, discrete=False):
        """
        Get the intention score of the entity during carry out, computed by the min distance to the entity.
        """
        if discrete:
            return int(self.intention_distance[entity_name] < threshold)
        else:
            if threshold - self.intention_distance[entity_name] < 0:
                return 0
            return 1 / (1 + (threshold - self.intention_distance[entity_name]) + 1e-6)


class PrimitiveSeqTask(PrimitiveTask):
    """
    An extended version of PrimitiveTask that supports sequential condition parsing (asyn_sequence, or).
    Key property: once a condition is met it is locked and never reverts (once met, always met).

    It differs from PrimitiveTask only in the `init_conditions` method:
    - Supports `asyn_sequence`: check multiple ConditionSets in order
    - Supports `or`: any single ConditionSet being satisfied is enough
    - Supports plain single-level conditions (e.g. contain_v, on), consistent with the parent class

    Config format examples:

    1. Plain condition (same as PrimitiveTask):
       {"contain_v": {"container": "plate_0", "entities": ["steak_0"], "vel_th": 0.01}}

    2. asyn_sequence (asynchronous sequential conditions):
       {
         "asyn_sequence": {
           "condition_sets": [
             {"contain": {"container": "pan_0", "entities": ["steak_0"]}},
             {"contain_v": {"container": "plate_0", "entities": ["steak_0"], "vel_th": 0.01}}
           ],
           "ordered_indices": [0, 1]
         }
       }

    3. or (any one satisfies):
       {
         "or": {
           "condition_sets": [
             {"contain_v": {"container": "plate_0", "entities": ["steak_0"]}},
             {"contain_v": {"container": "pan_0", "entities": ["steak_0"]}}
           ]
         }
       }

    4. Combined usage (outer asyn_sequence, inner or):
       {
         "asyn_sequence": {
           "condition_sets": [
             {"or": {"condition_sets": [...]}},
             {"contain_v": {...}}
           ],
           "ordered_indices": [0, 1]
         }
       }
    """

    def _resolve_condition_value(self, value):
        """
        Resolve values in the condition config, replacing entity names in strings/lists
        with the corresponding entity objects.
        """
        if isinstance(value, str):
            resolved = self.entities.get(value, None)
            return resolved if resolved is not None else value
        elif isinstance(value, list):
            return [self._resolve_condition_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._resolve_condition_value(v) for k, v in value.items()}
        return value

    def _build_condition_from_config(self, condition_key, specific_condition):
        """
        Build a Condition object from a condition key and its config.
        Supports recursively building nested asyn_sequence and or structures.
        """
        condition_cls = register.load_condition(condition_key)

        # Special conditions that require recursive construction: asyn_sequence, or
        if condition_key in ("asyn_sequence", "or"):
            condition_sets_config = specific_condition.get("condition_sets", [])
            ordered_indices = specific_condition.get("ordered_indices", None)

            condition_sets = []
            for cs_config in condition_sets_config:
                # cs_config is a dict, e.g. {"contain_v": {...}, "on": {...}}
                cs_conditions = []
                for ck, sc in cs_config.items():
                    sub_condition = self._build_condition_from_config(ck, copy.deepcopy(sc))
                    cs_conditions.append(sub_condition)
                condition_sets.append(ConditionSet(cs_conditions))

            if condition_key == "asyn_sequence":
                return AsynSequenceCondition(condition_sets=condition_sets, ordered_indices=ordered_indices)
            elif condition_key == "or":
                return OrCondition(condition_sets=condition_sets)

        # Handle plain conditions (contain_v, on, contact, etc.)
        resolved_config = {}
        skip_keys = {"positions", "target_pos_range", "container_name", "ordered_indices", "condition_sets"}

        for k, entities in specific_condition.items():
            if k in skip_keys:
                resolved_config[k] = entities
                continue
            if k == "robot":
                resolved_config[k] = self.robot
                continue
            if k == "target_bbox":
                resolved_config[k] = entities
                continue

            resolved_config[k] = self._resolve_condition_value(entities)

        return condition_cls(**resolved_config)

    def init_conditions(self):
        if self.config["task"].get("conditions", None) is not None:
            condition_config = copy.deepcopy(self.config["task"]["conditions"])
        else:
            self.conditions = None
            return False

        conditions = []
        for condition_key, specific_condition in condition_config.items():
            # Support and_conditions: a list of dicts, each dict is one condition config
            if condition_key == "and_conditions" and isinstance(specific_condition, list):
                for item in specific_condition:
                    for ck, sc in item.items():
                        condition = self._build_condition_from_config(ck, copy.deepcopy(sc))
                        conditions.append(condition)
                        if ck in ["contain_robot_pose"]:
                            self.navigation_condition = condition
                continue

            # Support or in list format (ClusterTask style):
            # [{"contain_1": {...}, "contain_2": {...}}, ...]
            # Keys with a "contain_" prefix (contain_1/contain_2 etc.) in each dict are
            # converted to contain, forming a ConditionSet (AND); multiple dicts form an OrCondition
            if condition_key == "or" and isinstance(specific_condition, list):
                condition_sets = []
                for branch_config in specific_condition:
                    branch_conditions = []
                    for ck, sc in branch_config.items():
                        if "contain_" in ck:
                            ck = "contain"
                        sub_condition = self._build_condition_from_config(ck, copy.deepcopy(sc))
                        branch_conditions.append(sub_condition)
                    condition_sets.append(ConditionSet(branch_conditions))
                condition = OrCondition(condition_sets=condition_sets)
                conditions.append(condition)
                continue

            condition = self._build_condition_from_config(condition_key, copy.deepcopy(specific_condition))
            conditions.append(condition)

            if condition_key in ["contain_robot_pose"]:
                self.navigation_condition = condition

        self.conditions = ConditionSet(conditions)
        return True
