import scriptcontext as sc
import clr, socket, threading, Rhino, json
clr.AddReference("System")
clr.AddReference("System.Drawing")
clr.AddReference("Grasshopper")
from System import Action
from System.Drawing import RectangleF
import Grasshopper
import Grasshopper as gh
import Rhino.Geometry as rg
import System
from System import Guid
from Grasshopper.Kernel import GH_ParamAccess
from Grasshopper.Kernel.Parameters import Param_GenericObject
from Grasshopper.Kernel.Parameters import Param_String, Param_Number, Param_Integer, Param_Boolean


class GHEncoder(json.JSONEncoder):
    """Custom JSON encoder for Grasshopper/Rhino types"""
    def default(self, obj):
        if isinstance(obj, rg.Point3d):
            return {
                "x": float(obj.X),
                "y": float(obj.Y),
                "z": float(obj.Z)
            }
        elif isinstance(obj, RectangleF):
            return {
                "x": float(obj.X),
                "y": float(obj.Y),
                "width": float(obj.Width),
                "height": float(obj.Height)
            }
        return json.JSONEncoder.default(self, obj)

# Use scriptcontext.sticky as a persistent dictionary.
if "command" not in sc.sticky:
    sc.sticky["command"] = None
if "server_running" not in sc.sticky:
    sc.sticky["server_running"] = False
if "last_result" not in sc.sticky:
    sc.sticky["last_result"] = None
if "server_thread" not in sc.sticky:
    sc.sticky["server_thread"] = None


def get_param_info(param, is_input=True, parent_instance_guid=None, simplified=False, is_selected=False):
    """Collect information from a Grasshopper parameter."""
    if simplified:
        # Simplified param info with just connections
        info = {
            "instanceGuid": str(param.InstanceGuid),
            "name": param.Name,
            "sources": [],
            "targets": [],
            "isSelected": is_selected
        }
        
        # Get sources (inputs)
        if hasattr(param, "Sources"):
            for src in param.Sources:
                try:
                    info["sources"].append(str(src.InstanceGuid))
                except:
                    pass
        
        # Get targets (outputs)
        if hasattr(param, "Recipients"):
            for tgt in param.Recipients:
                try:
                    info["targets"].append(str(tgt.InstanceGuid))
                except:
                    pass
                    
        # If this is a component param, add its parent to targets or sources
        if parent_instance_guid:
            if is_input and str(parent_instance_guid) not in info["targets"]:
                info["targets"].append(str(parent_instance_guid))
            elif not is_input and str(parent_instance_guid) not in info["sources"]:
                info["sources"].append(str(parent_instance_guid))
        
        return info
    
    # Detailed param info
    try:
        bounds_rect = RectangleF(
            param.Attributes.Bounds.X, 
            (param.Attributes.Bounds.Y * -1) - param.Attributes.Bounds.Height, 
            param.Attributes.Bounds.Width, 
            param.Attributes.Bounds.Height
        )
        pivot_pt = rg.Point3d(param.Attributes.Pivot.X, param.Attributes.Pivot.Y * -1, 0)
        
        param_info = {
            "instanceGuid": str(param.InstanceGuid),
            "parentInstanceGuid": str(parent_instance_guid) if parent_instance_guid else None,
            "bounds": bounds_rect,
            "pivot": pivot_pt,
            "dataMapping": str(param.DataMapping) if hasattr(param, 'DataMapping') else None,
            "dataType": str(param.TypeName) if hasattr(param, 'TypeName') else None,
            "simplify": str(param.Simplify) if hasattr(param, 'Simplify') else None,
            "name": param.Name,
            "nickName": param.NickName,
            "category": param.Category,
            "subCategory": param.SubCategory,
            "description": param.Description,
            "kind": str(param.Kind) if hasattr(param, 'Kind') else None,
            "sources": [],
            "targets": [],
            "isSelected": is_selected
        }
        
        # Add specific input parameter properties
        if is_input:
            try:
                param_info["InputAccess"] = str(param.Access)
            except Exception as e:
                param_info["InputAccess"] = "N/A"
            try:
                param_info["dataTypeHint"] = str(param.TypeHint)
            except Exception as e:
                param_info["dataTypeHint"] = "N/A"

        # Get sources (inputs)
        for src in param.Sources:
            try:
                param_info["sources"].append(str(src.InstanceGuid))
            except:
                pass

        # Get targets (outputs)
        for tgt in param.Recipients:
            try:
                param_info["targets"].append(str(tgt.InstanceGuid))
            except:
                pass
                
        # If this is a component param, add its parent to targets or sources
        if parent_instance_guid:
            if is_input and str(parent_instance_guid) not in param_info["targets"]:
                param_info["targets"].append(str(parent_instance_guid))
            elif not is_input and str(parent_instance_guid) not in param_info["sources"]:
                param_info["sources"].append(str(parent_instance_guid))

        return param_info
    except Exception as e:
        print("Error getting param info: " + str(e))
        return None

def get_component_info(comp, simplified=False, is_selected=False):
    """Collect information from a Grasshopper component."""
    if simplified:
        # Simplified component info
        info = {
            "instanceGuid": str(comp.InstanceGuid),
            "name": comp.Name,
            "nickName": comp.NickName,
            "description": comp.Description,
            "pivot": {"X": float(comp.Attributes.Pivot.X), "Y": float(comp.Attributes.Pivot.Y)} if (hasattr(comp, "Attributes") and comp.Attributes) else {},
            "inputs": [],
            "outputs": [],
            "sources": [],
            "targets": [],
            "isSelected": is_selected
            
        }
        
        try:
            info["runTimeMessage"]= str(component.RuntimeMessages(component.RuntimeMessageLevel)).replace("List[str]","")
        except:
            pass
        # Get input and output parameter info
        if hasattr(comp, "Params"):
            if hasattr(comp.Params, "Input"):
                info["inputs"] = [get_param_info(p, is_input=True, parent_instance_guid=comp.InstanceGuid, simplified=True) for p in comp.Params.Input]
            if hasattr(comp.Params, "Output"):
                info["outputs"] = [get_param_info(p, is_input=False, parent_instance_guid=comp.InstanceGuid, simplified=True) for p in comp.Params.Output]
        
        return info
    
    # Get component kind with fallback
    try:
        kind = str(comp.Kind) if hasattr(comp, 'Kind') else str(comp.__class__.__name__)
    except:
        kind = str(comp.__class__.__name__)
    
    # Basic info for all components
    comp_info = {
        "instanceGuid": str(comp.InstanceGuid),
        "name": comp.Name,
        "nickName": comp.NickName,
        "description": comp.Description,
        "category": comp.Category,
        "subCategory": comp.SubCategory,
        "kind": kind,
        "sources": [],
        "targets": [],
        "isSelected": is_selected
    }
    
    try:
        comp_info["runTimeMessage"]= str(component.RuntimeMessages(component.RuntimeMessageLevel)).replace("List[str]","")
    except:
        pass
    # Add additional info for non-standard components
    if kind != "component":
        comp_info.update({
            "bounds": RectangleF(
                comp.Attributes.Bounds.X, 
                (comp.Attributes.Bounds.Y * -1) - comp.Attributes.Bounds.Height, 
                comp.Attributes.Bounds.Width, 
                comp.Attributes.Bounds.Height
            ),
            "pivot": rg.Point3d(comp.Attributes.Pivot.X, comp.Attributes.Pivot.Y * -1, 0),
            "dataMapping": None,
            "dataType": None,
            "simplify": None,
            "computiationTime": float(comp.ProcessorTime.Milliseconds),
            "dataCount": None,
            "pathCount": None
        })
    
    # If the component is a script component, add its code.
    if comp.SubCategory == "Script":
        if hasattr(comp, "Code"):
            comp_info["Code"] = comp.Code
            #checks if code 
            comp_info["codeReferenceFromFile"] = comp.InputIsPath
            # if so check if we can get the file path
            if comp.InputIsPath:
                try:
                    for p in comp.Params.Input:
                        if p.Name == "code" and p.VolatileDataCount > 0:
                            comp_info["codeReferencePath"] = str(p.VolatileData.get_DataItem(0))
                            break
                except:
                    pass
        else:
            comp_info["Code"] = "none"
    
    # Get input and output parameter info if available.
    if hasattr(comp, "Params"):
        if hasattr(comp.Params, "Input"):
            comp_info["Inputs"] = [get_param_info(p, is_input=True, parent_instance_guid=comp.InstanceGuid) for p in comp.Params.Input]
        if hasattr(comp.Params, "Output"):
            comp_info["Outputs"] = [get_param_info(p, is_input=False, parent_instance_guid=comp.InstanceGuid) for p in comp.Params.Output]
    
    return comp_info

def get_standalone_param_info(param, simplified=False, is_selected=False):
    """Collect information for standalone parameters (sliders, panels, etc.)"""
    return get_param_info(param, is_input=False, simplified=simplified, is_selected=is_selected)

def sort_graph_by_execution_order(graph):
    """
    Sort the graph dictionary by component execution order.
    
    Args:
        graph: The graph dictionary containing component and parameter information
    
    Returns:
        A new graph dictionary with keys ordered by execution sequence
    """
    # Create a dictionary to store in-degrees (number of incoming edges)
    in_degree = {node_id: 0 for node_id in graph}
    
    # Calculate in-degree for each node
    for node_id, node_info in graph.items():
        if "targets" in node_info:
            for target_id in node_info["targets"]:
                if target_id in in_degree:
                    in_degree[target_id] += 1
    
    # Queue with nodes that have no incoming edges (in-degree = 0)
    queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
    
    # List to store the sorted order
    sorted_order = []
    
    # Process nodes in the queue
    while queue:
        # Get the next node
        current_id = queue.pop(0)
        sorted_order.append(current_id)
        
        # Reduce in-degree of all targets (downstream components)
        if "targets" in graph[current_id]:
            for target_id in graph[current_id]["targets"]:
                if target_id in in_degree:
                    in_degree[target_id] -= 1
                    # If in-degree becomes 0, add to queue
                    if in_degree[target_id] == 0:
                        queue.append(target_id)
    
    # For any remaining nodes (cycles or unreachable), add to the end
    remaining_nodes = [node_id for node_id in graph if node_id not in sorted_order]
    sorted_order.extend(remaining_nodes)
    
    # Create a new ordered dictionary
    ordered_graph = {}
    for node_id in sorted_order:
        if node_id in graph:
            ordered_graph[node_id] = graph[node_id]
    
    return ordered_graph

def get_objects(instance_guids, context_depth=0, simplified=False):
    """
    Get Grasshopper objects by their instance GUIDs with optional context.
    Focuses on retrieving components and standalone parameters.
    Returns a dictionary keyed by instance GUID, sorted by execution order.
    (Simplified revision to address complexity issues)
    """
    doc = ghenv.Component.OnPingDocument()
    if not doc:
        sc.sticky["processing_error"] = "get_objects: No active Grasshopper document."
        return {}

    if not isinstance(instance_guids, list):
        instance_guids = [str(instance_guids)]
    else:
        instance_guids = [str(g) for g in instance_guids]

    initial_target_guids = set(instance_guids)
    result_graph = {} # Stores info for components and standalone params
    guids_added_to_result = set() # Track what's already in the result

    # --- Build a map of all potential objects and their basic types/parents ---
    object_map = {} # {guid_str: {'obj': obj, 'is_comp': bool, 'is_param': bool, 'parent_guid': str|None}}
    for obj in doc.Objects:
        if not hasattr(obj, "InstanceGuid"): continue
        guid_str = str(obj.InstanceGuid)
        parent_guid = None
        parent_comp = obj.Attributes.Parent if hasattr(obj, "Attributes") and obj.Attributes else None
        if parent_comp and hasattr(parent_comp, "InstanceGuid"):
            parent_guid = str(parent_comp.InstanceGuid)

        object_map[guid_str] = {
            'obj': obj,
            'is_comp': isinstance(obj, Grasshopper.Kernel.IGH_Component),
            'is_param': isinstance(obj, Grasshopper.Kernel.IGH_Param),
            'parent_guid': parent_guid
        }

    # --- Pass 1: Process initially requested GUIDs ---
    guids_to_process_for_context = set()
    for target_guid_str in initial_target_guids:
        if target_guid_str in object_map:
            item = object_map[target_guid_str]
            obj_to_add = None
            obj_guid_to_add = None
            is_selected_flag = True # This object was directly requested

            if item['is_comp']:
                # Selected object is a component
                obj_to_add = item['obj']
                obj_guid_to_add = target_guid_str
            elif item['is_param']:
                if item['parent_guid']:
                    # Selected object is a component parameter - add the parent component instead
                    parent_guid_str = item['parent_guid']
                    if parent_guid_str in object_map:
                        obj_to_add = object_map[parent_guid_str]['obj']
                        obj_guid_to_add = parent_guid_str
                        # Mark the parent as selected since its child was selected?
                        # Let's keep the component info function handling isSelected for the component itself.
                        # We just need to ensure the parent component is included.
                    else:
                        # Parent component not found? Log error maybe.
                        sc.sticky["processing_error"] = sc.sticky.get("processing_error", "") + \
                            "\nWarning: Parent component {} not found for selected param {}.".format(item['parent_guid'], target_guid_str)
                else:
                    # Selected object is a standalone parameter
                    obj_to_add = item['obj']
                    obj_guid_to_add = target_guid_str
            # else: Handle other selected types if needed? For now, focus on comp/param.

            # If we identified a component or standalone param to add, get its info
            if obj_to_add and obj_guid_to_add and obj_guid_to_add not in guids_added_to_result:
                info = None
                if isinstance(obj_to_add, Grasshopper.Kernel.IGH_Component):
                    info = get_component_info(obj_to_add, simplified=simplified, is_selected=(obj_guid_to_add in initial_target_guids))
                elif isinstance(obj_to_add, Grasshopper.Kernel.IGH_Param): # Standalone only branch
                    info = get_standalone_param_info(obj_to_add, simplified=simplified, is_selected=(obj_guid_to_add in initial_target_guids))

                if info:
                    result_graph[obj_guid_to_add] = info
                    guids_added_to_result.add(obj_guid_to_add)
                    guids_to_process_for_context.add(obj_guid_to_add) # Use this GUID for context traversal


    # --- Pass 2: Traverse Context ---
    if context_depth > 0 and guids_to_process_for_context:
        # Build simplified link graph *only* for components and standalone params needed for traversal
        link_graph = {} # {guid: {"sources": [...], "targets": [...]}}
        for guid_str, item in object_map.items():
            node_sources = []
            node_targets = []
            current_obj = item['obj']

            if item['is_comp']:
                # Component: sources from inputs, targets from outputs
                if hasattr(current_obj.Params, "Input"):
                    for p in current_obj.Params.Input:
                        if hasattr(p, "Sources"):
                            node_sources.extend([str(src.InstanceGuid) for src in p.Sources if src and hasattr(src,"InstanceGuid")])
                if hasattr(current_obj.Params, "Output"):
                    for p in current_obj.Params.Output:
                        if hasattr(p, "Recipients"):
                             # Target is the recipient param itself, or its parent component if it has one
                             for recipient in p.Recipients:
                                  if recipient and hasattr(recipient, "InstanceGuid"):
                                      rec_guid = str(recipient.InstanceGuid)
                                      rec_parent = recipient.Attributes.Parent if hasattr(recipient, "Attributes") and recipient.Attributes else None
                                      if rec_parent and hasattr(rec_parent,"InstanceGuid"):
                                          node_targets.append(str(rec_parent.InstanceGuid)) # Target the component
                                      else:
                                           node_targets.append(rec_guid) # Target the standalone param

            elif item['is_param'] and not item['parent_guid']: # Standalone parameter
                # Standalone Param: sources from its sources, targets are its recipients
                if hasattr(current_obj, "Sources"):
                    node_sources.extend([str(src.InstanceGuid) for src in current_obj.Sources if src and hasattr(src,"InstanceGuid")])
                if hasattr(current_obj, "Recipients"):
                    # Target is the recipient param itself, or its parent component if it has one
                    for recipient in current_obj.Recipients:
                        if recipient and hasattr(recipient, "InstanceGuid"):
                            rec_guid = str(recipient.InstanceGuid)
                            rec_parent = recipient.Attributes.Parent if hasattr(recipient, "Attributes") and recipient.Attributes else None
                            if rec_parent and hasattr(rec_parent,"InstanceGuid"):
                                node_targets.append(str(rec_parent.InstanceGuid)) # Target the component
                            else:
                                node_targets.append(rec_guid) # Target the standalone param

            if node_sources or node_targets:
                 # Only add nodes that actually have connections relevant to components/standalone params
                 link_graph[guid_str] = {"sources": list(set(node_sources)), "targets": list(set(node_targets))}

        # --- Perform Traversal ---
        context_guids_to_add = set()
        visited_for_context = set(guids_to_process_for_context) # Start with the identified core items
        current_level = set(guids_to_process_for_context)
        max_depth = min(int(context_depth), 3)

        for _ in range(max_depth):
            next_level = set()
            for guid in current_level:
                if guid in link_graph:
                    node_links = link_graph[guid]
                    # Add upstream (sources)
                    for src in node_links.get("sources", []):
                        if src in object_map and src not in visited_for_context: # Check if src is a valid obj in our map
                             # Only add components or standalone params as context
                             if object_map[src]['is_comp'] or (object_map[src]['is_param'] and not object_map[src]['parent_guid']):
                                  next_level.add(src)
                                  visited_for_context.add(src)
                                  context_guids_to_add.add(src)
                    # Add downstream (targets)
                    for tgt in node_links.get("targets", []):
                        if tgt in object_map and tgt not in visited_for_context: # Check if tgt is valid
                            if object_map[tgt]['is_comp'] or (object_map[tgt]['is_param'] and not object_map[tgt]['parent_guid']):
                                next_level.add(tgt)
                                visited_for_context.add(tgt)
                                context_guids_to_add.add(tgt)

            if not next_level: break
            current_level = next_level

        # --- Pass 3: Get info for context objects ---
        for context_guid_str in context_guids_to_add:
            if context_guid_str not in guids_added_to_result: # Avoid reprocessing
                if context_guid_str in object_map:
                    item = object_map[context_guid_str]
                    info = None
                    is_selected_flag = False # Context objects are not selected

                    if item['is_comp']:
                        info = get_component_info(item['obj'], simplified=simplified, is_selected=is_selected_flag)
                    elif item['is_param'] and not item['parent_guid']: # Standalone only
                        info = get_standalone_param_info(item['obj'], simplified=simplified, is_selected=is_selected_flag)

                    if info:
                        result_graph[context_guid_str] = info
                        guids_added_to_result.add(context_guid_str)


    # --- Final Step: Sort the resulting graph ---
    # No need to filter child params here, as we only added components and standalone params
    if result_graph:
        return sort_graph_by_execution_order(result_graph)
    else:
        return {}


def get_object_by_instance_guid(doc, instance_guid):
    """
    Helper function to get an object from document by instance GUID string.
    
    Args:
        doc: Grasshopper document
        instance_guid: Instance GUID string
    
    Returns:
        Grasshopper object if found, None otherwise
    """
    try:
        import System
        if isinstance(instance_guid, str):
            instance_guid = System.Guid(instance_guid)
        
        for obj in doc.Objects:
            if obj.InstanceGuid == instance_guid:
                return obj
    except:
        pass
    
    return None
    
# ======== edit code component 


def update_script_component(instance_guid, code=None, description=None, message_to_user=None, param_definitions=None):
    """
    Updates a script component identified by its GUID with new code, description,
    a user message, and optionally new input/output parameters.
    
    Args:
        instance_guid (str): The GUID of the target script component.
        code (str, optional): New code for the component.
        description (str, optional): New component description.
        message_to_user (str, optional): Message to set on an output parameter.
        param_definitions (list of dict, optional): List of dictionaries defining parameters.
            Each dictionary must have:
              - "type": "input" or "output"
              - "name": a string
            Optional keys for inputs:
              - "access": "item", "list", or "tree" (default "list")
              - "typehint": e.g. "str", "int", "float", "bool" (determines parameter type)
              - "description": text to display for the parameter (falls back to default_description)
              - "optional": bool, default True
              - "default": a default value (not set persistently)
    
    Returns:
        dict: Status and result details.
    """
    default_description="Dynamically added parameter"
    # always set mesage_to_user as output
    #code = code + "\n\n# Display message to user\noutput = " + repr(message_to_user)
    try:
        # Get the Grasshopper document and find the target component by instance GUID.
        doc = ghenv.Component.OnPingDocument()
        target_instance_guid = Guid.Parse(instance_guid)
        comp = doc.FindObject(target_instance_guid, False)
        if comp is None:
            return {"status": "error", "result": "Component with instance GUID {} not found.".format(instance_guid)}
        
        
        gh.Instances.ActiveCanvas.Enabled = False

        try:
            # If parameter definitions are provided, update parameters.
            if param_definitions is not None:
                try:
                    # Step 1: Add temporary dummy parameters to prevent crashes
                    dummy_input = create_input_param({"description": "Temporary parameter"}, "__dummy_input__", default_description)
                    dummy_output = create_output_param({"description": "Temporary parameter"}, "__dummy_output__")
                    
                    comp.Params.RegisterInputParam(dummy_input)
                    comp.Params.RegisterOutputParam(dummy_output)
                    
                    # Step 2: Clear existing inputs and outputs (except dummies)
                    for p in list(comp.Params.Input):
                        if p.Name != "__dummy_input__":
                            comp.Params.UnregisterInputParameter(p)
                            
                    for p in list(comp.Params.Output):
                        if p.Name != "__dummy_output__":
                            comp.Params.UnregisterOutputParameter(p)
                    
                    # Step 3: Process and add the new parameters
                    # Process inputs
                    inputs = [d for d in param_definitions if d.get("type", "").lower() == "input"]
                    for d in inputs:
                        if "name" not in d:
                            continue
                        name = d["name"]
                        new_param = create_input_param(d, name, default_description)
                        comp.Params.RegisterInputParam(new_param)
                    
                    # Process outputs
                    outputs = [d for d in param_definitions if d.get("type", "").lower() == "output"]
                    for d in outputs:
                        if "name" not in d:
                            continue
                        name = d["name"]
                        new_param = create_output_param(d, name)
                        comp.Params.RegisterOutputParam(new_param)
                    
                    # Ensure there is always an output parameter named "output"
                    out_names = [d.get("name", "").lower() for d in outputs]
                    if "output" not in out_names:
                        default_out = create_output_param({"description": "Default output"}, "output")
                        comp.Params.RegisterOutputParam(default_out)
                    
                    # Step 4: Remove the dummy parameters now that we have real parameters
                    comp.Params.UnregisterInputParameter(dummy_input)
                    comp.Params.UnregisterOutputParameter(dummy_output)
                    
                    # Clear component data and cache
                    comp.ClearData()
                    
                except Exception as e:
                    return {"status": "error", "result": "Error updating parameters: {}".format(str(e))}
            
            # Update code if provided.
            if code is not None:
                try:
                    if hasattr(comp, "Code"):
                        comp.Code = code
                    else:
                        return {"status": "error", "result": "Component does not have a Code attribute. Component type: {}".format(type(comp).__name__)}
                except Exception as e:
                    return {"status": "error", "result": "Error updating code: {}".format(str(e))}
            
            # Update component description if provided.
            if description is not None:
                try:
                    comp.Description = description
                except Exception as e:
                    return {"status": "error", "result": "Error updating description: {}".format(str(e))}
            
            # Set a message to the user if provided (attempting to add volatile data to first output).
            if message_to_user is not None:
                try:
                    if hasattr(comp, "Params") and hasattr(comp.Params, "Output") and len(comp.Params.Output) > 0:
                        comp.Params.Output[0].AddVolatileData(Grasshopper.Kernel.Data.GH_Path(0), 0, message_to_user)
                except Exception as e:
                    return {"status": "error", "result": "Error setting message: {}".format(str(e))}
            
            # Force component to recompute.
            if hasattr(comp, "Attributes"):
                comp.Attributes.ExpireLayout()
            comp.ExpireSolution(True)
            
            return {
                "status": "success",
                "result": {
                    "code_updated": code is not None,
                    "description_updated": description is not None,
                    "message_set": message_to_user is not None,
                    "component_type": type(comp).__name__
                }
            }
        finally:
            # CRITICAL: Always unfreeze the UI, even if an error occurs
            doc.DestroyAttributeCache()
            gh.Instances.ActiveCanvas.Enabled = True

    except Exception as e:
        return {"status": "error", "result": "General error updating component: {}".format(str(e))}
        
        
def get_access(access_str):
    """
    Convert a string ("item", "list", or "tree") to GH_ParamAccess.
    Defaults to list.
    """
    if isinstance(access_str, basestring):
        s = access_str.lower()
        if s == "item":
            return GH_ParamAccess.item
        elif s == "tree":
            return GH_ParamAccess.tree
    return GH_ParamAccess.list

def create_input_param(d, name, default_description):
    """
    Creates an input parameter based on the dictionary.
    Chooses a parameter type based on 'typehint' if provided.
    Does not set the TypeHint property to keep the right-click menu active.
    """
    hint = d.get("typehint", "").lower()
    if hint in ["str", "string"]:
        param = Param_String()
    elif hint in ["int", "integer"]:
        param = Param_Integer()
    elif hint in ["float", "number", "double"]:
        param = Param_Number()
    elif hint in ["bool", "boolean"]:
        param = Param_Boolean()
    else:
        param = Param_GenericObject()
    
    param.NickName = name
    param.Name = name
    param.Description = d.get("description", default_description)
    param.Access = get_access(d.get("access", "list"))
    param.Optional = d.get("optional", True)
   
    return param

def create_output_param(d, name):
    """
    Creates an output parameter.
    For outputs, we simply create a generic parameter.
    """
    param = Param_GenericObject()
    param.NickName = name
    param.Name = name
    param.Description = d.get("description", "Dynamically added output")
    
    return param
    
    
    
def update_script_with_code_reference(instance_guid, file_path=None, param_definitions=None, description=None, name=None, force_code_reference=False):
    """
    Updates a script component to use code from an external file.
    """
    doc = ghenv.Component.OnPingDocument()
    target_guid = System.Guid.Parse(instance_guid)
    comp = doc.FindObject(target_guid, False)
    
    if comp is None:
        return {"status": "error", "result": "Component not found"}
    
    result = {"status": "error", "result": "Unknown error"}
    
    # Freeze the canvas
    gh.Instances.ActiveCanvas.Enabled = False
    
    try:
        if force_code_reference:
            # APPROACH 1: Try to completely reset the component's internal state
            
            # First, clear any existing code
            if hasattr(comp, "Code"):
                # Set component's code to a minimal script that forces external code usage
                comp.Code = "# This component is set to use external code"
            
            # Toggle InputIsPath off and on
            comp.InputIsPath = False
            comp.InputIsPath = True
            
            # Remove any existing code parameter
            for p in list(comp.Params.Input):
                if p.Name == "code":
                    comp.Params.UnregisterInputParameter(p)
            
            # Create fresh code parameter
            code_param = comp.ConstructCodeInputParameter()
            code_param.NickName = "code"
            code_param.Name = "code"
            code_param.Description = "Path to Python code file"
            
            # Force a rebuild of the component
            comp.ClearData()
            comp.Attributes.ExpireLayout()
            comp.ExpireSolution(True)
            doc.DestroyAttributeCache()
            
            # Register the parameter
            comp.Params.RegisterInputParam(code_param)
            
            # Set InputIsPath again
            comp.InputIsPath = True
            
            # Set file path if provided
            if file_path is not None:
                code_param.AddVolatileData(Grasshopper.Kernel.Data.GH_Path(0), 0, file_path)
            
            # APPROACH 2: Try manipulating document-level features to force update
            comp.Phase = Grasshopper.Kernel.GH_SolutionPhase.Blank  # Reset solution phase
            
            # Force the component to be "dirty" to ensure recomputation
            if hasattr(comp, "OnPingDocument"):
                comp_doc = comp.OnPingDocument()
                if comp_doc:
                    comp_doc.ScheduleSolution(5)  # Schedule a solution update
        
        # Handle param definitions but preserve code input
        if param_definitions is not None:
            default_description = "Dynamically added parameter"
            
            # Add temporary dummy parameters
            dummy_input = create_input_param({"description": "Temporary parameter"}, "__dummy_input__", default_description)
            dummy_output = create_output_param({"description": "Temporary parameter"}, "__dummy_output__")
            
            comp.Params.RegisterInputParam(dummy_input)
            comp.Params.RegisterOutputParam(dummy_output)
            
            # Clear existing inputs/outputs except code input and dummies
            for p in list(comp.Params.Input):
                if p.Name != "__dummy_input__" and p.Name != "code":
                    comp.Params.UnregisterInputParameter(p)
                    
            for p in list(comp.Params.Output):
                if p.Name != "__dummy_output__":
                    comp.Params.UnregisterOutputParameter(p)
            
            # Add new inputs (skip code parameter)
            inputs = [d for d in param_definitions if d.get("type", "").lower() == "input" 
                      and d.get("name", "").lower() != "code"]
            
            for d in inputs:
                if "name" not in d:
                    continue
                name_val = d["name"]
                new_param = create_input_param(d, name_val, default_description)
                comp.Params.RegisterInputParam(new_param)
            
            # Add new outputs
            outputs = [d for d in param_definitions if d.get("type", "").lower() == "output"]
            for d in outputs:
                if "name" not in d:
                    continue
                name_val = d["name"]
                new_param = create_output_param(d, name_val)
                comp.Params.RegisterOutputParam(new_param)
            
            # Ensure there's always an output parameter
            out_names = [d.get("name", "").lower() for d in outputs]
            if "output" not in out_names:
                default_out = create_output_param({"description": "Default output"}, "output")
                comp.Params.RegisterOutputParam(default_out)
            
            # Remove dummy parameters
            comp.Params.UnregisterInputParameter(dummy_input)
            comp.Params.UnregisterOutputParameter(dummy_output)
        
        # Update description and name if provided
        if description is not None:
            comp.Description = description
        
        if name is not None:
            comp.NickName = name
        
        # Final force update
        comp.ClearData()
        comp.Attributes.ExpireLayout()
        comp.ExpireSolution(True)
        
        result = {
            "status": "success",
            "result": {
                "code_reference_enforced": force_code_reference,
                "file_path_set": file_path is not None,
                "description_updated": description is not None,
                "name_updated": name is not None
            }
        }
    except Exception as e:
        result = {"status": "error", "result": str(e) + " remember in case of erros/bugs in code you need to fix it in the reference python file "}
    finally:
        # Always unfreeze the UI
        doc.DestroyAttributeCache()
        gh.Instances.ActiveCanvas.Enabled = True
    
    return result
    

#======

def get_selected_components(simplified=False, context_depth=0):
    """
    Get currently selected components and parameters in the Grasshopper document.
    
    Args:
        simplified: Whether to return simplified object info
        context_depth: How many levels up/downstream to include (0-3)
    
    Returns:
        Dictionary of selected objects, keyed by their instance GUID
    """
    # Get the current Grasshopper document
    doc = ghenv.Component.OnPingDocument()
    if not doc:
        return {"error": "No active Grasshopper document"}
    
    # Find all selected objects
    selected_guids = []
    for obj in doc.Objects:
        if hasattr(obj, "Attributes") and hasattr(obj.Attributes, "Selected") and obj.Attributes.Selected:
            selected_guids.append(str(obj.InstanceGuid))
    
    # If no objects are selected, return empty result
    if not selected_guids:
        return {}
    
    # Use the existing get_objects function to get details about the selected objects
    # This also handles the context_depth parameter
    result = get_objects(selected_guids, context_depth=context_depth, simplified=simplified)
    
    return result

def get_grasshopper_context(simplified=False):
    """
    Get information about the current Grasshopper document and its components.
    
    Args:
        simplified: Whether to return simplified graph info
    
    Returns:
        Dictionary with graph information, always sorted by execution order
    """
    try:
        # Get the current Grasshopper document
        doc = ghenv.Component.OnPingDocument()
        if not doc:
            return {"error": "No active Grasshopper document"}

        # Initialize graph dictionary
        IO_graph = {}

        # Get all objects in the document
        for obj in doc.Objects:
            is_selected = hasattr(obj, "Attributes") and hasattr(obj.Attributes, "Selected") and obj.Attributes.Selected
            
            if isinstance(obj, Grasshopper.Kernel.IGH_Component):
                comp_info = get_component_info(obj, simplified=simplified, is_selected=is_selected)
                IO_graph[str(obj.InstanceGuid)] = comp_info
            elif isinstance(obj, Grasshopper.Kernel.IGH_Param):
                # Handle standalone parameters
                param_info = get_standalone_param_info(obj, simplified=simplified, is_selected=is_selected)
                IO_graph[str(obj.InstanceGuid)] = param_info

        # Fill in sources based on targets for comprehensive connections
        for node_id, node in IO_graph.items():
            for target_id in node["targets"]:
                if target_id in IO_graph and node_id not in IO_graph[target_id]["sources"]:
                    IO_graph[target_id]["sources"].append(node_id)

        # Always sort the graph by execution order
        if IO_graph:
            IO_graph = sort_graph_by_execution_order(IO_graph)

        return {
            "status": "success",
            "graph": IO_graph
        }
    except Exception as e:
        print("Error in get_grasshopper_context: " + str(e))
        return {"error": str(e)}

def receive_full_request(conn):
    """Receive the complete HTTP request."""
    data = b''
    while True:
        chunk = conn.recv(1048576)
        if not chunk:
            break
        data += chunk
        if b'\r\n\r\n' in data:  # Found end of headers
            break
    return data.decode('utf-8')

def respond(conn, response_dict):
    """Send an HTTP response with JSON content and close the connection."""
    json_response = json.dumps(response_dict, cls=GHEncoder)
    http_response = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: {}\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Connection: close\r\n"
        "\r\n"
        "{}"
    ).format(len(json_response), json_response)
    try:
        conn.sendall(http_response.encode('utf-8'))
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except:
            pass

def parse_command(data):
    """Parse the incoming command data into a structured format."""
    try:
        command_data = json.loads(data)
        if isinstance(command_data, dict):
            return command_data
        return {"type": "raw", "data": data}
    except json.JSONDecodeError:
        return {"type": "raw", "data": data}

def execute_code(code_str):
    """Execute Python code string and return the result."""
    try:
        # Create a new dictionary for local variables
        local_vars = {}
        
        # Execute the code with access to the current context
        exec(code_str, globals(), local_vars)
        
        # If there's a result variable defined, return it
        if 'result' in local_vars:
            return {"status": "success", "result": local_vars['result']}
        return {"status": "success", "result": "Code executed successfully"}
    except Exception as e:
        print("Code execution error: " + str(e))
        return {"status": "error", "result": str(e)}

def process_command(command_data):
    """Process a command and return the result."""
    command_type = command_data.get("type", "raw")
    
    if command_type == "raw":
        # Handle legacy raw text commands
        raw_data = command_data["data"]
        if raw_data == "fetch_new_data":
            return {"result": "Fetched new data!", "status": "success"}
        else:
            return {"result": "Unknown command: " + raw_data, "status": "error"}
            
    elif command_type == "test_command":
        # Handle test command with dummy response
        params = command_data.get("params", {})
        return {
            "status": "success",
            "result": {
                "message": "Test command executed successfully",
                "received_params": params,
                "dummy_data": {"value": 42, "text": "Hello from Grasshopper!"}
            }
        }
        
    elif command_type == "get_context":
        # Get Grasshopper context, with option for simplified view
        simplified = command_data.get("simplified", False)
        context = get_grasshopper_context(simplified=simplified)
        if "error" in context:
            return {"status": "error", "result": context}
        return {
            "status": "success",
            "result": context
        }
        
    elif command_type == "get_object" or command_type == "get_objects":
        # Get objects by instance GUIDs with optional context depth
        if command_type == "get_object":
            instance_guid = command_data.get("instance_guid")
            if not instance_guid:
                return {"status": "error", "result": "No instance GUID provided"}
            instance_guids = [instance_guid]
        else:
            instance_guids = command_data.get("instance_guids", [])
            if not instance_guids:
                return {"status": "error", "result": "No instance GUIDs provided"}
            
        simplified = command_data.get("simplified", False)
        context_depth = command_data.get("context_depth", 0)
        
        # Validate context_depth (0-3)
        try:
            context_depth = int(context_depth)
            if context_depth < 0:
                context_depth = 0
            elif context_depth > 3:
                context_depth = 3
        except:
            context_depth = 0
            
        result = get_objects(instance_guids, context_depth=context_depth, simplified=simplified)
        
        if not result:
            return {"status": "error", "result": "Objects not found"}
            
        return {
            "status": "success",
            "result": result
        }
        
    elif command_type == "get_selected":
        # Get selected components/parameters with optional context
        simplified = command_data.get("simplified", False)
        context_depth = command_data.get("context_depth", 0)
        
        # Validate context_depth (0-3)
        try:
            context_depth = int(context_depth)
            if context_depth < 0:
                context_depth = 0
            elif context_depth > 3:
                context_depth = 3
        except:
            context_depth = 0
            
        selected = get_selected_components(simplified=simplified, context_depth=context_depth)
        return {
            "status": "success",
            "result": selected
        }
        
    elif command_type == "update_script":
        # Update a script component (now also accepting param_definitions)
        # Accept either instance_guid or component_guid (for backward compatibility)
        instance_guid = command_data.get("instance_guid")
        if not instance_guid:
            # Fall back to component_guid if instance_guid is not provided
            instance_guid = command_data.get("component_guid")
            if not instance_guid:
                return {"status": "error", "result": "No instance_guid provided"}
        
        code = command_data.get("code")
        description = command_data.get("description")
        message_to_user = command_data.get("message_to_user")
        # New: Get dynamic parameter definitions if supplied.
        param_definitions = command_data.get("param_definitions")
        
        result = update_script_component(
            instance_guid, 
            code=code, 
            description=description, 
            message_to_user=message_to_user,
            param_definitions=param_definitions  
        )
        
        return result
        
    elif command_type == "update_script_with_code_reference":
        # Update a script component to use code from an external file
        # Accept either instance_guid or component_guid (for backward compatibility)
        instance_guid = command_data.get("instance_guid")
        if not instance_guid:
            # Fall back to component_guid if instance_guid is not provided
            instance_guid = command_data.get("component_guid")
            if not instance_guid:
                return {"status": "error", "result": "No instance_guid provided"}
        
        # Get parameters for the update operation
        file_path = command_data.get("file_path")
        param_definitions = command_data.get("param_definitions")
        description = command_data.get("description")
        name = command_data.get("name")
        force_code_reference = command_data.get("force_code_reference", False)
        
        result = update_script_with_code_reference(
            instance_guid, 
            file_path=file_path,
            param_definitions=param_definitions,
            description=description,
            name=name,
            force_code_reference=force_code_reference
        )
        
        return result
        
    elif command_type == "execute_code":
        # Execute Python code
        code = command_data.get("code", "")
        if not code:
            return {"status": "error", "result": "No code provided"}
        return execute_code(code)
        
    else:
        return {"result": "Unknown command type: " + command_type, "status": "error"}

def socket_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    host = "127.0.0.1"  # Bind to localhost
    port = 9999         # Use port 9999
    s.bind((host, port))
    s.listen(5)         # Allow up to 5 pending connections
    print("Socket server listening on {}:{}".format(host, port))
    A = "Socket server listening on 127.0.0.1:9999"
    
    while True:
        try:
            s.settimeout(1.0)  # Check for new connections every second.
            try:
                conn, addr = s.accept()
                conn.settimeout(5.0)  # Set timeout for receiving data
            except socket.timeout:
                continue
            
            try:
                full_data = receive_full_request(conn)
                if full_data:
                    sc.sticky["fullData"] = full_data
                if not full_data:
                    continue
                
                # Extract the payload from the HTTP request (ignoring headers)
                parts = full_data.split("\r\n\r\n")
                if len(parts) > 1:
                    command = parts[1].strip()
                else:
                    command = full_data.strip()
                
                # Parse the command into a structured format
                command_data = parse_command(command)
                sc.sticky["commandData"] = command_data
                print("Received command: " + str(command_data))

                # Handle stop command
                if command_data.get("type") == "stop":
                    print("Received stop command. Closing server.")
                    respond(conn, {"status": "stopping", "message": "Server is shutting down."})
                    conn.close()
                    break

                # Process command immediately and store result
                result = process_command(command_data)
                sc.sticky["last_result"] = result
                
                # Send response with result
                response = {
                    "status": result["status"],
                    "result": result["result"],
                    "command_type": command_data.get("type", "raw")
                }
                respond(conn, response)
            except Exception as e:
                print("Error handling request: " + str(e))
                error_response = {
                    "status": "error",
                    "result": str(e)+ str(sc.sticky["last_result"]),
                    "command_type": "error"
                }
                respond(conn, error_response)
            finally:
                try:
                    conn.close()
                except:
                    pass
        except Exception as e:
            print("Socket server error: " + str(e)+ str(sc.sticky["last_result"]))
            break
    s.close()
    sc.sticky["server_running"] = False
    print("Socket server closed.")

# Start the socket server if it isn't already running.
if not sc.sticky["server_running"]:
    sc.sticky["server_running"] = True
    thread = threading.Thread(target=socket_server)
    thread.daemon = True
    thread.start()

# Main SolveInstance processing:
if sc.sticky["last_result"]:
    result = sc.sticky["last_result"]
    sc.sticky["last_result"] = None  # Clear the result after processing
    A = "Last command result: " + json.dumps(result, cls=GHEncoder)  # Use custom encoder here too
   
else:
    A = "Waiting for command..."