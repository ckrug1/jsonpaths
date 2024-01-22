import stat
import pandas as pd
from datetime import datetime
from dataclasses import KW_ONLY, dataclass, field
from typing import List, Dict, Any, Optional
from copy import deepcopy 
import string 
import random 
from pprint import pprint
from pathlib import Path

from .jshcema import JPSchema
from .jshcema import SchemaTypes
from .jshcema import OBJECT_IN_ARRAY, OBJECT_IN_OBJECT, ARRAY_IN_OBJECT, FIELD_IN_OBJECT
from copy import deepcopy
from dateutil import parser
import json 


@dataclass
class JsonPaths:
    """
    A class for generating and analyzing JSON schema paths.

    Attributes:
        json_file (Any): The JSON data to analyze.
        rootname (str): The root name for the JSON schema.
        delim (str): The delimiter used to separate JSON path components.
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
    _: KW_ONLY
    rootname: str = 'root'
    delim: str = '.'
    sample_limit:int = field(default=500)
    fallback_delimter:str = field(default='<>')
    json_schema: Optional[List[Dict[str, Any]]] = field(default_factory=list,init=False)
    flattened_obj: List[Dict] = field(default_factory=list,init=False)
    jpschema:JPSchema = field(default_factory=JPSchema,init=False)
    object_descendants: List[str] = field(default_factory=list,init=False)
    __previous_delim:str = field(default=None,init=False)
    __used_fallback:bool = field(default=False,init=False)
    __is_schema_loaded:bool = field(default=False,init=False)

    def __post_init__(self):
        pass 
        #self.json_schema = list()
        
    
    @staticmethod
    def _analyze_types(value):
        val_replace = {"STR":"STRING","INT":"INTEGER","NONETYPE":"NULL","BOOL":"BOOLEAN"}
        type_value = str(type(value).__name__).upper()
        type_value = val_replace.get(type_value,type_value)
        if not type_value == "STRING":
            return type_value
        string_len = len(value)
        if string_len < 9: #Min length to be considered a date 
            return type_value
        try:
            parser.isoparse(value)
            return "DATETIME"
        except ValueError:
            return type_value
    # @staticmethod
    # def _try_date_convert(value):
    #     dt = parser.parse(value)
        
    

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
            del type_dict["NULL"]
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
        check_all = [self.fallback_delimter not in x.get('full_path') for x in self.jpschema.schema_obj.values()]
        
        if not all(check_all):
            self.fallback_delimter = self.id_generator(size=2)
        self.__previous_delim = self.delim
        self.delim = self.fallback_delimter
        self.__used_fallback = True 
        self.fallback_delimter = self.id_generator(size=2)
        rep_values = lambda y: y if not isinstance(y,str) else y.replace(self.__previous_delim,self.delim)
        new_allitems = dict() 
        if self.jpschema.schema_obj:
            for key in self.jpschema.schema_obj.keys():
                new_key = key.replace(self.__previous_delim,self.delim)
                values = self.jpschema.schema_obj.get(key)
                #print('TEST: ','KEY: ' , key, values)
                new_values = {k:v if k not in ['full_path','parent_path'] else rep_values(v) for k,v in values.items()}
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
        if self.__is_schema_loaded:
            raise Exception("Schema is already loaded, re-initialize the class to load schema again.")
            
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
        self.__is_schema_loaded = True 
        
        
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
                         include_parent_flds:list = [],
                         ignore_fields:list = [],
                         include_fields:list = [],
                         flatten_inner_objects:bool=True,
                         try_datetime_conversion:bool=False):
        """
        Retrieves objects from the JSON data based on a given path.
        Args:
            object_path (str): The path of the target JSON object. Required. 
            return_type (str, optional): The return type ('records' or 'dataframe'). Defaults to 'records'.
            new_json_file (Any, optional): A new JSON data file to use. Defaults to None.
            topic (str, optional): The topic name for the root JSON object. Defaults to 'root'.
            collapse_parent_fields (list, optional): List of parent fields to bring in with the parent object_path. 
            example: 
                object_path = 'root.value.artists.albums'
                
                collapse_parent_fields = ['root.value.artists.id','root.value.artists.name']
                
                This will return everything in albums as well as the two fields specified in artists (if they exist)
                
            Alternatively, an asterisk can be used to select all fields from a parent object.
            
            example: 
                object_path = 'root.value.artists.albums'
                
                collapse_parent_fields = ['root.value.artists.*']
                
                This will return everything in albums as well as everything in artists.     
                
            flatten_inner_objects (bool, optional): Whether to flatten inner objects. Defaults to True. Does not flatten arrays of objects, as that would alter the underlying structure resulting in duplications.
            try_datetime_conversion (bool,optional): Whether to attempt converting datetime type strings to datetime python objects. 
            include_fields (list, optional): List of fields to be included in the returned values. The list of fields should be comprised of the full paths to them.
            ignore_fields (list, optional): List of fields to ignore. Takes precedence over include fields.

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
                if remaining_objects and self._flatten_inner_objects:
                    
                    for key, val in remaining_objects.items():
                        if isinstance(val,list) and not isinstance(val[0],(list,dict,type(None))):
                            inner_vals = {f'{item_name}_{key}': ', '.join([str(valstr) for valstr in val]) }
                            isdupeskeys = [x for x in inner_vals.keys() if x in list(self.flattened_vals.keys())]
                            if isdupeskeys:
                                parent_item = self.jpschema.get_parent_item(f'{object_path}{self.delim}{key}').get('parent_name')
                                inner_vals = {f'{parent_item}_{x}':y for x,y in inner_vals.items() if not isinstance(y, (dict,list))}
                                
                            self.flattened_vals = dict(**self.flattened_vals,**inner_vals)

                        if isinstance(val,dict):
                            
                    
                            inner_vals = {f'{key}_{x}':y for x,y in val.items() if not isinstance(y, (dict,list))}
                            isdupeskeys = [x for x in inner_vals.keys() if x in list(self.flattened_vals.keys())]
                            if isdupeskeys:
                                #parent_path = self.jpschema.schema_obj.get(f'{object_path}{self.delim}{key}').get('parent_path')
                                parent_item = self.jpschema.get_parent_item(f'{object_path}{self.delim}{key}').get('parent_name')
                                inner_vals = {f'{parent_item}_{x}':y for x,y in inner_vals.items() if not isinstance(y, (dict,list))}
                                
                            #key_check = {k:v for k,v  in inner_vals.items() if k in }
                            self.flattened_vals = dict(**self.flattened_vals,**inner_vals)

    
                            inner_remaining = {x:y for x,y in val.items() if isinstance(y,(list,dict))}

                            if inner_remaining:
                                flatten_object(inner_remaining,self.jpschema.schema_obj.get(f'{object_path}{self.delim}{key}'))
                
                if current_obj_schema.get('full_path') == self._object_path:
                    if parent_fields:
                        self.flattened_vals.update(parent_fields)
                    
    
                    self.flattened_obj.append(self.flattened_vals)
                    self.flattened_vals = dict()


        def find_relatives(item_path:str):
            direct_descendants = [x.get('full_path') for x in self.json_schema if x.get('parent_path') == item_path and x.get('other_info') != 'OBJECT_IN_ARRAY']
            indirect_descendants = [x for x in direct_descendants]
            while True:
                if not indirect_descendants:
                    break 
                itm = indirect_descendants.pop()
                chk = [s.get('full_path') for s in self.json_schema if s.get('parent_path') == itm]
                indirect_descendants.extend(chk)
                if chk:
                    direct_descendants.extend(chk)
            child_fields = []
            current_path = item_path 
            while True:
                pitem = self.jpschema.get_parent_item(current_path)
                ppath = pitem.get('full_path')

                pfields = [x.get('full_path') for x in self.json_schema if x.get('parent_path') == ppath and x.get('other_info') == 'FIELD_IN_OBJECT']
                if pfields:
                    child_fields.extend(pfields)
                if ppath == self.rootname:
                    break 
                current_path = ppath 
            self.object_ascendants = child_fields
            self.object_descendants = direct_descendants
    

        def check_parent_fields(current_obj,current_obj_schema):

            if not isinstance(current_obj,dict):
                return None 
            if not self._include_parent_flds:
                return 
            fld_paths = [f'{current_obj_schema.get("parent_path")}{self.delim}{x}' for x in current_obj.keys()]
            check_matches = [p.split(self.delim)[-1] for p in fld_paths if p in self._include_parent_flds]
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
                    
        def _check_collapse_parent_flds():
            star_strings = [x.replace(f'{self.delim}*','') for x in self._include_parent_flds if x.endswith('*')]
            self._include_parent_flds = [x for x in self._include_parent_flds if not x.endswith('*') and self.jpschema.schema_obj.get(x)]
            if star_strings:
                all_flds = [y.get('full_path') for x in star_strings for y in self.json_schema if y.get('parent_path') == x and y.get('other_info') == 'FIELD_IN_OBJECT' ]
                if all_flds:
                    self._include_parent_flds.extend(all_flds)
            
            self._include_parent_flds = [x for x in self._include_parent_flds if x in self.object_ascendants]    
                   
        
        
        if not self.json_schema:
            self.generate_schema()
        if new_json_file:
            self.json_file = new_json_file
        self.flattened_obj = list()
        self.flattened_vals = dict()
        self._object_path = object_path
        self._include_parent_flds = include_parent_flds
        self._flatten_inner_objects = flatten_inner_objects
        parent_fields = dict() 
        path_instructions = self.find_path(target_object=object_path)
        find_relatives(object_path)
        root = path_instructions.get('root')
        
        root['item_name'] = root_topic 
        root['item_path'] = root_topic 
        path_instructions[root_topic] = root 
        json_dict = [{root_topic:self.json_file}]
        
        if self._include_parent_flds:
            _check_collapse_parent_flds() 
        self.consumption_schema = self._create_consumption_schema(object_path)
        
        find_level(root_topic, json_dict) #main driver method. Recursively iterates over the data until specified path(s) are found. 
        
        if ignore_fields:
            self.flattened_obj = [{k:v for k,v in x.items() if k not in ignore_fields} for x in self.flattened_obj]
        if include_fields:
            self.flattened_obj = [{k:v for k,v in x.items() if k in include_fields} for x in self.flattened_obj]
        
        if try_datetime_conversion:
            self._try_convert_datetime()
        
        if return_type == 'records':
            return self.flattened_obj
        elif return_type == 'dataframe':
            return pd.DataFrame(self.flattened_obj)

    def save_schema_to_file(self,file_path:str,file_name:str=None):
        file_path = Path(file_path)
        if not file_path.exists(): #Checks if parent folders exist, if not creates them. 
                file_path.mkdir(parents=True,exist_ok=False)
        file_path = file_path.joinpath(file_name)
        with open(file_path,'w') as sfile:
            json.dump(self.jpschema.schema_obj,sfile,indent=3)
            
    def load_schema_from_file(self,file_path:str):
        with open(file_path,'r') as jfile:
            schema_obj = json.load(jfile)
        self.jpschema.schema_obj = schema_obj
        self.json_schema = [v for v in self.jpschema.schema_obj.values()]
        self.__is_schema_loaded = True 

    def _create_consumption_schema(self,object_path,replacements:dict=None):
        """Creates a schema that can be paired with the dictionaries returned in retrieve_objects method.

        Args:
            object_path (str): The path the schema should be based upon. 
            replacements (dict): Use to replace types; with key as default type and value as the replacement. 
        """

        consumption_schema = {}
        obj_desc = self.object_descendants


        for o in self.object_descendants:
            item_type = self.jpschema.schema_obj.get(o).get('item_type')
            if item_type in ['object','object_z']:
                continue 
            if not self._flatten_inner_objects:
                if self.jpschema.schema_obj.get(o).get('parent_path') != object_path:
                    continue
            
            relative_path = o.replace(object_path + self.delim,'')
            consumption_name = relative_path.replace(self.delim,'_')
            consumption_schema.update({consumption_name:item_type})
        if self._include_parent_flds:
            for co in self._include_parent_flds:
                item_def = self.jpschema.schema_obj.get(co)
                if not item_def:
                    continue
                consumption_name = item_def.get('parent_name') + '_' + item_def.get('item_name')
                item_type = item_def.get('item_type')
                consumption_schema.update({consumption_name:item_type})
                
        if replacements:
            consumption_schema = {k:replacements.get(v,v) for k,v in consumption_schema.items()}
            
        #consumption_schema_str = ', '.join([f"{k} {v}" for k,v in consumption_schema.items()])
        return consumption_schema
            
    def _try_convert_datetime(self,datetimetype_name:str='DATETIME'):
        def try_date_parse(value):
            try:
                dt = parser.isoparse(value)
                return dt 
            except Exception:
                return value
        
        dt_flds = [x for x in self.consumption_schema.keys() if self.consumption_schema.get(x) == datetimetype_name]
        if dt_flds:
            self.flattened_obj = [{k:try_date_parse(v) if k in dt_flds else v for k,v in x.items()} for x in self.flattened_obj]
            

# def enhance_json_schema(all_items:dict) -> dict: 
     
#     allitems = deepcopy(all_items)

#     def get_inferred_topic(jobj:dict):
#         item_name = jobj.get('item_name')
#         parent = jobj.get('parent_name')[:-1] if jobj.get('parent_name').endswith('s') else jobj.get('parent_name')
#         inferred_topic = f'{parent}_{item_name}'.lower()
#         return inferred_topic
    
#     def find_parent_obj(jobj:dict):
#         while jobj.get('other_info').lower() != 'object-in-array':
#             jobj = allitems.get(jobj.get('parent_path'))
#         return get_inferred_topic(jobj)

#     for obj in allitems.values():
#         depth = len(obj.get('full_path').split('.')) -1 
#         inferred_topic = get_inferred_topic(obj)
#         # if obj.get('item_type') == 'object' and obj.get('other_info') == 'NA': #
#         #     obj.update(dict(inferred_topic=inferred_topic,depth=depth,other_info='object-in-array',field_name='N/A'))


#     for obj in allitems.values():
#         depth = len(obj.get('full_path').split('.')) -1 
#         if obj.get('other_info').lower() == 'object-in-array':
#             continue
#         inferred_topic = find_parent_obj(obj)
#         #other_info = 'field' if not obj.get('other_info') else obj.get('other_info')
#         if obj.get('other_info').lower() == 'object-in-object':
#             field_name = 'N/A'
#         elif not inferred_topic.endswith(obj.get('parent_name').lower()):
#             field_name = f'{obj.get("parent_name")}_{obj.get("item_name")}'
#         else:
#             field_name = obj.get('item_name')
#         obj.update(dict(inferred_topic=inferred_topic,depth=depth,field_name=field_name))

                

            
#     return  allitems 












# Example usage:
# refreshablespath = './data/Refreshables/2023/11/refreshables_20231101_175127978.json'
# scanpath = '/workspaces/jsonpaths/dataset_refreshes_part_0_20240105_162009099.json'
# scanpath = '/workspaces/jsonpaths/usv_users.json'

# with open(scanpath, 'r') as f:
#     jfile = json.load(f)


# object_path = 'root.value'



# json_paths_instance = JsonPaths(jfile)
# schema = json_paths_instance.generate_schema()
# result = json_paths_instance.retrieve_objects(object_path='root.workspaces.datasets',collapse_parent_fields=['root.workspaces.id'])
# df = pd.DataFrame(result)
# print(df.cols)