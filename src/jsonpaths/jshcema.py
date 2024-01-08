
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


from enum import Enum



class SchemaTypes(Enum):

    OBJECT_IN_ARRAY = 'object'
    OBJECT_IN_OBJECT = 'object_z'
    ARRAY_IN_OBJECT = 'array'
    FIELD_IN_OBJECT = 'field'



OBJECT_IN_ARRAY, OBJECT_IN_OBJECT, ARRAY_IN_OBJECT, FIELD_IN_OBJECT = SchemaTypes.OBJECT_IN_ARRAY, SchemaTypes.OBJECT_IN_OBJECT, SchemaTypes.ARRAY_IN_OBJECT, SchemaTypes.FIELD_IN_OBJECT

@dataclass()
class JPSchema:

    schema_obj: dict = field(default_factory=dict)
    
    def _create_or_replace(self,full_path:str,item_type:SchemaTypes):
        item_obj = self.schema_obj.get(full_path) 
        if not item_obj:
            return True 
        if item_type.value == 'object' and item_obj.get('other_info') == 'FIELD_IN_OBJECT':
            return True 
        return False 
             
    def add_samples(self,full_path:str,sample_value:str):

        self.schema_obj[full_path]['sample_values'].append(sample_value)
        self.schema_obj[full_path]['samples_taken'] +=1

    def add_item(self,schema_type:SchemaTypes,full_path:str,delim):
        if self._create_or_replace(full_path=full_path,item_type=schema_type):
            path_parts = full_path.split(delim)
            pindex = -2 if len(path_parts) > 1  else -1 
            parent_path = path_parts[0] if pindex == -1 else delim.join(path_parts[:-1])
            self.schema_obj[full_path] = dict(full_path=full_path,
                                              item_name=path_parts[-1],
                                              parent_path=parent_path,
                                              parent_name=path_parts[pindex],
                                              sample_values=[],
                                              total_values=0,
                                              samples_taken=0,
                                              item_type=schema_type.value,
                                              is_nullable=False,
                                              other_info=schema_type.name)
        self.schema_obj[full_path]['total_values'] += 1
        #self.update(item_dict)

    def get_direct_child_flds(self,parent_path:str,item_type:SchemaTypes=None):
        direct_child_flds = []
        for x in self.schema_obj.values():
            if x.get('parent_path') == parent_path:
                if item_type and item_type.name != x.get('other_info'):
                    continue
                direct_child_flds.append(x)
        return direct_child_flds

            


    def get_parent_item(self,obj_key:str):
        
        parent_path = self.schema_obj.get(obj_key).get('parent_path')
        return self.schema_obj.get(parent_path)





__all__ = ['OBJECT_IN_ARRAY', 'OBJECT_IN_OBJECT', 'ARRAY_IN_OBJECT', 'FIELD_IN_OBJECT','JPSchema']