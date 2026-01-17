from ...globals import Physics, Tasks
from ..entity import Entity
from ...utils import Event


class Area(Entity):
    def __init__(self):
        self.ghost = None
        self._overlapping_entities = set()  # Track currently overlapping entities.
        self.target_groups = set()  # Groups to check overlaps against, but reject any other.
        self.avoid_groups = set()  # Groups to ignore overlaps with, does not work if there are target groups.

        super().__init__()

        # Set ghost body.
        self.ghost = Physics.create_ghost(name=self.get_name())

        # Check overlaps.
        Tasks.add_task(f'area_overlap_checker_{self.id}', self._check_overlaps)

        # Overlap events.
        self.on_begin_overlap = Event[Entity]()  # Called when entity enters.
        self.on_overlap = Event[Entity]()        # Called every frame while overlapping.
        self.on_end_overlap = Event[Entity]()    # Called when entity exits.
        self.on_rejected = Event[Entity]()       # Called when entity is rejected by filters.

    
    def _check_overlaps(self, task):
        if self.ghost is None:
            return task.cont
        
        # Get current overlapping nodes.
        current_nodes = self.ghost.getOverlappingNodes()
        current_entities = set()
        rejected_entities = set()

        # Collect entities from overlapping nodes.
        for node in current_nodes:
            if node.hasPythonTag('entity'):
                entity = node.getPythonTag('entity')
                if self._validate_overlap(entity):
                    current_entities.add(entity)
                else:
                    rejected_entities.add(entity)
        
        # Check for entities that started overlapping (on_begin_overlap).
        new_entities = current_entities - self._overlapping_entities
        for entity in new_entities:
            self.on_begin_overlap(entity)
        
        # Check for entities that are still overlapping (on_overlap).
        for entity in current_entities:
            self.on_overlap(entity)
        
        # Check for entities that stopped overlapping (on_end_overlap).
        removed_entities = self._overlapping_entities - current_entities
        for entity in removed_entities:
            self.on_end_overlap(entity)
        
        # Check for rejected entities.
        for entity in rejected_entities:
            self.on_rejected(entity)
        
        # Update the overlapping entities set.
        self._overlapping_entities = current_entities
        
        return task.cont
        

    def _validate_overlap(self, entity: Entity) -> bool:
        ''' Validate if the overlap with the given entity should be considered. '''
        entity_group = entity.get_collision_group()
        if self.target_groups and entity_group not in self.target_groups:
            return False

        if self.avoid_groups and entity_group in self.avoid_groups:
            return False
        
        return True

    def _get_node(self):
        return self.ghost