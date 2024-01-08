import pandas as pd
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from copy import deepcopy 
import string 
import random 
from pprint import pprint
from .jshcema import JPSchema
from .jshcema import SchemaTypes
from .jshcema import OBJECT_IN_ARRAY, OBJECT_IN_OBJECT, ARRAY_IN_OBJECT, FIELD_IN_OBJECT
from copy import deepcopy
@dataclass
class JsonPaths:
    """
    A class for generating and analyzing JSON schema paths.

    Attributes:
        json_file (Any): The JSON data to analyze.
        rootname (str): The root name for the JSON schema.
        delim (str): The delimiter used to separate JSON path components.
        allitems (Dict[str, Any]): A dictionary to store information about JSON path components.
        json_schema (Optional[List[Dict[str, Any]]]): The generated JSON schema.
        flattened_obj (List[Dict]): A list to store flattened JSON objects.

    Methods:
        _analyze_types(value): Analyzes the type of a JSON value.
        _find_occur(array_of_things): Counts occurrences of items in a list.
        _determine_type_result(type_dict): Determines the most common data type in a dictionary.
        recurse_objects(kv_object, parent, other_info='NA'): Recursively analyzes JSON objects.
        recurse_lists(array_obj, parent): Recursively analyzes JSON arrays.
        generate_schema(): Generates a JSON schema for the provided JSON data.
        find_path(target_object): Finds the path instructions for a target JSON object.
        retrieve_objects(object_path, return_type='records', new_json_file=None, topic='root', collapse_parent_fields=[], flatten_inner_objects=True): Retrieves objects from the JSON data based on a given path.
    """
    json_file: Any
    rootname: str = 'root'
    delim: str = '.'
    allitems: Dict[str, Any] = field(default_factory=dict)
    json_schema: Optional[List[Dict[str, Any]]] = None
    flattened_obj: List[Dict] = field(default_factory=list)
    object_descendants: List[str] = field(default_factory=list)
    sample_limit:int = field(default=500)
    jpschema:JPSchema = field(default_factory=JPSchema)
    _fallback_delimter:str = field(default='<>')
    _previous_delim:str = field(default=None)
    _usedfallback:bool = field(default=False)

    @staticmethod
    def _analyze_types(value):
        """
        Analyzes the type of a JSON value.
        Args:
            value: The JSON value to analyze.
        Returns:
            str: The data type of the value (BOOLEAN, INTEGER, DECIMAL, NULL, DATETIME, STRING, UNKNOWN).
        """
        if isinstance(value, bool):
            return "BOOLEAN"
        elif isinstance(value, int):
            return "INTEGER"
        elif isinstance(value, float):
            return "DECIMAL"
        elif isinstance(value,type(None)):
            return "NULL"
        elif isinstance(value, str):
            try:
                datetime.fromisoformat(value)
                return "DATETIME"
            except ValueError:
                return "STRING"
        
        return "UNKNOWN"

    @staticmethod
    def _find_occur(array_of_things: List):
        """
        Counts occurrences of items in a list.
        Args:
            array_of_things (List): The list of items to count occurrences for.
        Returns:
            Dict: A dictionary with items as keys and their occurrences as values.
        """
        def count_occurences(_item):
            unique_items[_item] +=1
        unique_items = {i:0 for i in list(set(array_of_things))}
        for itm in array_of_things:
            count_occurences(itm)
        return unique_items

    @staticmethod
    def _determine_type_result(type_dict: Dict):
        """
        Determines the most common data type in a dictionary.
        Args:
            type_dict (Dict): A dictionary with data types as keys and their occurrences as values.
        Returns:
            Dict: A dictionary with 'item_type' and 'is_nullable' keys.
        """
        isnullable = False 
        type_result = dict()
        valcount = 0 
        if "NULL" in list(type_dict.keys()):
            isnullable = True 
            if len(list(type_dict.keys())) < 2:
                return dict(item_type='STRING',is_nullable=isnullable)
        for itemkey, occurences in type_dict.items():
            if occurences > valcount:
                type_result['item_type'] = itemkey
                type_result['is_nullable'] = isnullable
                valcount = occurences

        return type_result
    
    @staticmethod
    def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
        id_inner = ''.join(random.choice(chars) for _ in range(size))
        return f'<{id_inner}>'

    def _check_delim(self,obj_key):
        if not self.delim in obj_key:
            return 
        check_all = [self._fallback_delimter not in x.get('full_path') for x in self.jpschema.schema_obj.values()]
        
        if not all(check_all):
            self._fallback_delimter = self.id_generator(size=2)
        self._previous_delim = self.delim
        self.delim = self._fallback_delimter
        self._usedfallback = True 
        self._fallback_delimter = self.id_generator(size=2)
        rep_values = lambda y: y if not isinstance(y,str) else y.replace(self._previous_delim,self.delim)
        new_allitems = dict() 
        if self.jpschema.schema_obj:
            for key in self.jpschema.schema_obj.keys():
                new_key = key.replace(self._previous_delim,self.delim)
                values = self.jpschema.schema_obj.get(key)
                #print('TEST: ','KEY: ' , key, values)
                new_values = {k:rep_values(v) for k,v in values.items()}
                #print('Key: ', key, 'Changed to: ', new_key)
                new_allitems[new_key] = new_values
                
            del self.jpschema.schema_obj
            self.jpschema.schema_obj = new_allitems

        
    def _handle_samples(self,full_path:str,val:Any):
        #self.jpschema.schema_obj = None 

        if self.jpschema.schema_obj.get(full_path).get('samples_taken') < self.sample_limit:
            self.jpschema.add_samples(full_path=full_path,sample_value=self._analyze_types(val))
   



    def _recurse_objects(self, kv_object: Dict, parent: str, schema_type:SchemaTypes=OBJECT_IN_ARRAY):
            """
            Recursively analyzes JSON objects.
            Args:
                kv_object (Dict): The JSON object to analyze.
                parent (str): The parent JSON path.
                other_info (str, optional): Additional information about the object. Defaults to 'NA'.
            """
            kv_pairs = {k:v for k,v in kv_object.items() if not isinstance(v,(list,dict))}
            #self.add_schema_object(parent=parent,other_info=other_info)
            self.jpschema.add_item(schema_type=schema_type,full_path=parent,delim=self.delim)

            for kv_key, kv_val in kv_pairs.items():
                #schema_def = self.add_schema_item(item_type='field',parent=parent,obj_key=kv_key)
                self.jpschema.add_item(schema_type=FIELD_IN_OBJECT,
                                       full_path=f'{parent}{self.delim}{kv_key}',
                                       delim=self.delim)
                #samples_taken = self.allitems.get(full_path).get('samples_taken')
                self._handle_samples(full_path=f'{parent}{self.delim}{kv_key}',val=kv_val)

            remaining_objects = {k:v for k,v in kv_object.items() if isinstance(v,(list,dict))}
            if not remaining_objects:
                return 
            
            for key, val in remaining_objects.items():
                if isinstance(val,dict):
                    self._check_delim(key)
                    self._recurse_objects(kv_object=val,parent=f'{parent}{self.delim}{key}',schema_type=OBJECT_IN_OBJECT)
                     
                if isinstance(val,list):
                    self._check_delim(key)
                    self._recurse_lists(array_obj=val,parent=f'{parent}{self.delim}{key}')
                    



    def _recurse_lists(self, array_obj, parent: str):
        """
        Recursively analyzes JSON arrays.
        Args:
            array_obj: The JSON array to analyze.
            parent (str): The parent JSON path.
        """
        for itm in array_obj:
            if not isinstance(itm,(list,dict)):
                # This is for objects that look like this: {"key1": ["value2", "value3", "value4"]"}
                # self.add_schema_object(parent=parent,)
                
                self.jpschema.add_item(schema_type=ARRAY_IN_OBJECT,
                                       full_path=parent,
                                       delim=self.delim)
                self._handle_samples(full_path=parent,val=itm)
                #self.jpschema.add_samples(full_path=parent,sample_value=self._analyze_types(itm))
                #self.allitems[fullpath]['sample_values'].append(self._analyze_types(itm))
            if isinstance(itm,dict):
                self._recurse_objects(kv_object=itm,parent=parent,schema_type=OBJECT_IN_ARRAY)
            if isinstance(itm,list):
                self._recurse_lists(array_obj=itm,parent=parent)

    def generate_schema(self):
        """
        Generates a JSON schema for the provided JSON data.
        Returns:
            List[Dict[str, Any]]: The generated JSON schema as a list of dictionaries.
        """
        if not isinstance(self.json_file, list):
            self.json_file = [self.json_file]

        self._recurse_lists(array_obj=self.json_file, parent=self.rootname)
        for fld_key, fld_val in self.jpschema.schema_obj.items():
            sample = fld_val.get('sample_values')
            if sample:
                type_result = self._determine_type_result(self._find_occur(sample))
                fld_val.update(type_result)
            del fld_val['sample_values']
        self.json_schema = [v for v in self.jpschema.schema_obj.values()]
        
        
        return self.json_schema

    def find_path(self, target_object: str):
        """
        Finds the path instructions for a target JSON object.
        Args:
            target_object (str): The target JSON object's path.
        Returns:
            Dict: Path instructions as a dictionary."""
        instr = dict()
        newstruct = {fld.get('full_path'):fld  for fld in self.json_schema}
        if not newstruct.get(target_object):
            raise Exception("Object not found in existing schema!")
        all_items = target_object.split(self.delim)
        paths = [self.delim.join(all_items[0:i]) for i in range(1,len(all_items) +1) ]
        for i, p in enumerate(paths):
            navs = newstruct.get(p)
            if not i + 2 > len(paths):
                navs['next_item'] = newstruct.get(paths[i+1]).get('item_name')
                navs['next_path'] = newstruct.get(paths[i+1]).get('full_path')
            else:
                navs['next_item'] = 'STOP'
                navs['next_path'] = 'STOP'
            instr.update({p:navs})
        return instr

    def retrieve_objects(self, 
                         object_path: str,
                         return_type:str='records',
                         new_json_file:Any = None, 
                         root_topic: str = 'root', 
                         collapse_parent_fields:list = [],
                         flatten_inner_objects:bool=True):
        """
        Retrieves objects from the JSON data based on a given path.
        Args:
            object_path (str): The path of the target JSON object.
            return_type (str, optional): The return type ('records' or 'dataframe'). Defaults to 'records'.
            new_json_file (Any, optional): A new JSON data file to use. Defaults to None.
            topic (str, optional): The topic name for the root JSON object. Defaults to 'root'.
            collapse_parent_fields (list, optional): List of parent fields to collapse. Defaults to an empty list.
            flatten_inner_objects (bool, optional): Whether to flatten inner objects. Defaults to True.

        Returns:
            List[Dict] or pd.DataFrame: Retrieved JSON objects as a list of dictionaries or a DataFrame.
        """
        
  
        def flatten_object(current_obj,current_obj_schema:dict):
            if not current_obj:
                return None 
            
            if isinstance(current_obj,dict):
                current_obj = [current_obj]
            object_path = current_obj_schema.get('full_path')
            item_name = current_obj_schema.get('item_name')
            for _ in current_obj:
                if not self.flattened_vals:
                    self.flattened_vals = dict()
                inner_remaining = dict() 
                self.flattened_vals.update({x:y for x,y in _.items() if not isinstance(y, (list,dict))})
                remaining_objects = {x:y for x,y in _.items() if isinstance(y,(dict,list)) and f'{object_path}{self.delim}{x}' in self.object_descendants and y}
                if remaining_objects:
                    
                    for key, val in remaining_objects.items():
                        if isinstance(val,list) and not isinstance(val[0],(list,dict,type(None))):
                            inner_vals = {f'{item_name}_{key}': ', '.join([str(valstr) for valstr in val]) }
                            self.flattened_vals = dict(**self.flattened_vals,**inner_vals)

                        if isinstance(val,dict):
                            
                    
                            inner_vals = {f'{key}_{x}':y for x,y in val.items() if not isinstance(y, (dict,list))}
                            self.flattened_vals = dict(**self.flattened_vals,**inner_vals)

    
                            inner_remaining = {x:y for x,y in val.items() if isinstance(y,(list,dict))}

                            if inner_remaining:
                                flatten_object(inner_remaining,self.jpschema.schema_obj.get(f'{object_path}{self.delim}{key}'))
                
                if current_obj_schema.get('other_info') == 'OBJECT_IN_ARRAY':
                    if parent_fields:
                        self.flattened_vals.update(parent_fields)
                    
    
                    self.flattened_obj.append(self.flattened_vals)
                    self.flattened_vals = dict()


        def find_descendants(item_path:str):
            direct_descendants = [x.get('full_path') for x in self.json_schema if x.get('parent_path') == item_path and x.get('other_info') != 'OBJECT_IN_ARRAY']
            indirect_descendants = list()
            for x in direct_descendants:
                chk = [s.get('full_path') for s in self.json_schema if s.get('parent_path') == x]
                if chk:
                    indirect_descendants.extend(chk)

            direct_descendants.extend(indirect_descendants)
            return direct_descendants

        def check_parent_fields(current_obj,current_obj_schema):

            if not isinstance(current_obj,dict):
                return None 
            
            fld_paths = [f'{current_obj_schema.get("parent_path")}{self.delim}{x}' for x in current_obj.keys()]
            check_matches = [p.split(self.delim)[-1] for p in fld_paths if p in collapse_parent_fields]
            if check_matches:
                parent_d = {f'{current_obj_schema.get("parent_name")}_{x}':current_obj.get(x) for x in check_matches if not isinstance(current_obj.get(x),(list,dict,type(None)))}
                parent_fields.update(parent_d)

        def find_level(item_path,current_obj):
            current_obj_schema = path_instructions.get(item_path)
            item_name = current_obj_schema.get('item_name')
            
            if not current_obj:
                return None
            if isinstance(current_obj,dict):
                current_obj = [current_obj]
            for o in current_obj:
                check_parent_fields(current_obj=o,current_obj_schema=current_obj_schema)
                if current_obj_schema.get('next_item') == 'STOP':
                    flatten_object(current_obj=o.get(item_name),
                                 current_obj_schema=current_obj_schema)
                else:
                    item = o.get(item_name) if isinstance(o,dict) else o
                    if not item:
                        continue
                    next_path = current_obj_schema.get('next_path') if isinstance(o,dict) else item_path
                    find_level(item_path=next_path, 
                               current_obj=item)

        if not self.json_schema:
            self.generate_schema()
        if new_json_file:
            self.json_file = new_json_file
        self.flattened_obj = list()
        self.flattened_vals = dict()
        parent_fields = dict() 
        path_instructions = self.find_path(target_object=object_path)
        self.object_descendants = find_descendants(object_path)
        root = path_instructions.get('root')
        root['item_name'] = root_topic 
        root['item_path'] = root_topic 
        path_instructions[root_topic] = root 
        json_dict = [{root_topic:self.json_file}]
    
        find_level(root_topic, json_dict)
        if return_type == 'records':
            return self.flattened_obj
        elif return_type == 'dataframe':
            return pd.DataFrame(self.flattened_obj)





def enhance_json_schema(all_items:dict) -> dict: 
     
    allitems = deepcopy(all_items)

    def get_inferred_topic(jobj:dict):
        item_name = jobj.get('item_name')
        parent = jobj.get('parent_name')[:-1] if jobj.get('parent_name').endswith('s') else jobj.get('parent_name')
        inferred_topic = f'{parent}_{item_name}'.lower()
        return inferred_topic
    
    def find_parent_obj(jobj:dict):
        while jobj.get('other_info').lower() != 'object-in-array':
            jobj = allitems.get(jobj.get('parent_path'))
        return get_inferred_topic(jobj)

    for obj in allitems.values():
        depth = len(obj.get('full_path').split('.')) -1 
        inferred_topic = get_inferred_topic(obj)
        # if obj.get('item_type') == 'object' and obj.get('other_info') == 'NA': #
        #     obj.update(dict(inferred_topic=inferred_topic,depth=depth,other_info='object-in-array',field_name='N/A'))


    for obj in allitems.values():
        depth = len(obj.get('full_path').split('.')) -1 
        if obj.get('other_info').lower() == 'object-in-array':
            continue
        inferred_topic = find_parent_obj(obj)
        #other_info = 'field' if not obj.get('other_info') else obj.get('other_info')
        if obj.get('other_info').lower() == 'object-in-object':
            field_name = 'N/A'
        elif not inferred_topic.endswith(obj.get('parent_name').lower()):
            field_name = f'{obj.get("parent_name")}_{obj.get("item_name")}'
        else:
            field_name = obj.get('item_name')
        obj.update(dict(inferred_topic=inferred_topic,depth=depth,field_name=field_name))

                

            
    return  allitems 












# Example usage:
# refreshablespath = './data/Refreshables/2023/11/refreshables_20231101_175127978.json'
# refreshablespath = './data/Refreshables/2023/11/refreshables_20231115_173559991.json'
# scanpath = './src/data/scan_results/workspace_scan_results_20230601_130851205.json'

# with open(scanpath, 'r') as f:
#     jfile = json.load(f)


# object_path = 'root.value'



# json_paths_instance = JsonPaths(jfile)
# schema = json_paths_instance.generate_schema()
# result = json_paths_instance.retrieve_objects(object_path='root.workspaces.datasets',collapse_parent_fields=['root.workspaces.id'])
# df = pd.DataFrame(result)
# print(df.cols)