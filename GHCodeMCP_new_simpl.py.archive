import scriptcontext as sc
import clr
import socket
import threading
import Rhino # Added
import Rhino.Geometry as rg # Added from old
import json
import traceback # Added
import time # Added
import System # Keep existing System import
from System import Guid, Action # Added Action
from System.Drawing import RectangleF
import Grasshopper
import Grasshopper as gh
from Grasshopper.Kernel import GH_ParamAccess, IGH_Param, GH_RuntimeMessageLevel # Added IGH_Param, GH_RuntimeMessageLevel
from Grasshopper.Kernel.Parameters import ( # Added specific Param types
    Param_GenericObject, Param_String, Param_Number,
    Param_Integer, Param_Boolean, Param_Guid, Param_Point,
    Param_Vector, Param_Curve, Param_Surface, Param_Brep, Param_Mesh
)
# --- Constants ---
HOST = "127.0.0.1"
PORT = 9999
COMPONENT_NICKNAME = "MCP Server" # Added

# --- JSON Encoding ---
class GHEncoder(json.JSONEncoder):
    """Custom JSON encoder for Grasshopper/Rhino types (incorporates Guid)"""
    def default(self, obj):
        if isinstance(obj, System.Guid): # Added Guid handling
            return str(obj)
        elif isinstance(obj, rg.Point3d):
            return {"x": float(obj.X), "y": float(obj.Y), "z": float(obj.Z)}
        elif isinstance(obj, RectangleF):
            # Use Y inversion from newer script for screen coords
            return {"x": float(obj.X), "y": float(obj.Y), "width": float(obj.Width), "height": float(obj.Height)}
        # Fallback for other types
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            # Fallback to representation string if direct encoding fails
            return repr(obj)

# --- Script Context Sticky Management ---
# Use descriptive keys inspired by GHCodeMCP.py, initialized simply
default_sticky = {
    "run_server": False, # Control flag for server loop
    "server_is_intended_to_run": False, # Tracks user intent via input toggle
    "server_thread_obj": None, # Stores the actual thread object
    "server_status": "Server Off", # User-facing status message
    "last_connection_addr": None, # Info about last connection
    "server_thread_error": None, # Errors from the server thread itself
    "processing_error": None, # Errors from process_command logic (incl. parsing)
    "last_update_error": None, # Specific errors from update functions
    "connection_log": None # Log messages from connection restoration
}
for key, value in default_sticky.items():
    if key not in sc.sticky:
        sc.sticky[key] = value

# --- Helper Functions (Parameter Type/Access Conversion - Adapted from GHCodeMCP.py) ---
def get_access_enum(access_str):
    """Converts string ('item', 'list', 'tree') to GH_ParamAccess enum."""
    if isinstance(access_str, str): # Check if it's a string
        s = access_str.lower()
        if s == "item":
            return GH_ParamAccess.item
        elif s == "tree":
            return GH_ParamAccess.tree
    # Default to list for unknown, None, or non-string values
    return GH_ParamAccess.list

def get_access_string(gh_param_access):
    """Converts GH_ParamAccess enum to string."""
    if gh_param_access == GH_ParamAccess.item:
        return "item"
    elif gh_param_access == GH_ParamAccess.tree:
        return "tree"
    else: # Default to list
        return "list"

def create_gh_input_param(param_def, default_description="Input parameter"):
    """
    Creates a Grasshopper input parameter from a definition dictionary.
    Uses enhanced type mapping like GHCodeMCP.py.
    """
    name = param_def.get("name", "input")
    # Use NickName if available and different from Name, otherwise use Name
    nick_name = param_def.get("nickName", name)
    if not nick_name: nick_name = name # Ensure NickName is not empty

    hint = param_def.get("typehint", "generic").lower()
    description = param_def.get("description", default_description)
    access = get_access_enum(param_def.get("access", "list"))
    optional = param_def.get("optional", True)

    # Choose parameter type based on hint (from GHCodeMCP.py)
    if hint == "str": param = Param_String()
    elif hint == "int": param = Param_Integer()
    elif hint == "float": param = Param_Number()
    elif hint == "bool": param = Param_Boolean()
    elif hint == "guid": param = Param_Guid()
    elif hint == "point": param = Param_Point()
    elif hint == "vector": param = Param_Vector()
    elif hint == "curve": param = Param_Curve()
    elif hint == "surface": param = Param_Surface()
    elif hint == "brep": param = Param_Brep()
    elif hint == "mesh": param = Param_Mesh()
    else: param = Param_GenericObject() # Default

    param.Name = name
    param.NickName = nick_name
    param.Description = description
    param.Access = access
    param.Optional = optional
    # Do not set param.TypeHint to allow user changes via context menu

    return param

def create_gh_output_param(param_def, default_description="Output parameter"):
    """Creates a Grasshopper output parameter from a definition dictionary."""
    name = param_def.get("name", "output")
    # Use NickName if available and different from Name, otherwise use Name
    nick_name = param_def.get("nickName", name)
    if not nick_name: nick_name = name # Ensure NickName is not empty

    description = param_def.get("description", default_description)

    # Outputs are typically generic unless specific typing is strictly needed
    param = Param_GenericObject()
    param.Name = name
    param.NickName = nick_name
    param.Description = description

    return param

# --- Grasshopper Object Information Functions (Based on GHCodeMCP_old_working.py, with improvements) ---

def get_param_info(param, is_input=True, parent_instance_guid=None, is_selected=False, simplified=False):
    """Collect detailed information from a Grasshopper parameter.
       Based on GHCodeMCP_old_working.py's structure, with Y-inversion and parent GUID.
       Includes a simplified mode.
    """
    guid_str = str(param.InstanceGuid)
    parent_guid_str = str(parent_instance_guid) if parent_instance_guid else None
    nick_name = param.NickName or param.Name # Prefer NickName

    # Calculate sources and targets regardless of simplified mode for consistency
    sources_list = []
    targets_list = []
    try:
        # Get sources (inputs to this param)
        if hasattr(param, "Sources"):
            sources_list = [str(src.InstanceGuid) for src in param.Sources if src]
        # Get targets (params receiving output from this param)
        if hasattr(param, "Recipients"):
            targets_list = [str(tgt.InstanceGuid) for tgt in param.Recipients if tgt]

        # If it's a component parameter, add parent connections
        if parent_guid_str:
            if is_input: # Input param's target is its parent component
                 if parent_guid_str not in targets_list:
                     targets_list.append(parent_guid_str)
            else: # Output param's source is its parent component
                 if parent_guid_str not in sources_list:
                     sources_list.append(parent_guid_str)
    except Exception as e_conn:
        # Log connection error simply
        error_msg = "Error getting connections for param {}: {}".format(guid_str, e_conn)
        existing_error = sc.sticky.get("processing_error", "")
        sc.sticky["processing_error"] = (existing_error + "\n" + error_msg).strip()

    if simplified:
        # Return minimal info focusing on identity and connectivity
        info = {
            "instanceGuid": guid_str,
            "parentInstanceGuid": parent_guid_str,
            "name": param.Name,
            "nickName": nick_name,
            "kind": "parameter", # Simplified kind identifier
            "sources": sources_list,
            "targets": targets_list,
            "isSelected": is_selected,
            "isInput": is_input,
        }
        return info

    # --- Detailed Parameter Information ---
    # Initialize with default values
    bounds_rect = {}
    pivot_pt = {}

    try:
        if hasattr(param, "Attributes") and param.Attributes:
            bounds = param.Attributes.Bounds
            # Use Y inversion for screen coords
            bounds_rect = RectangleF(bounds.X, (bounds.Y * -1) - bounds.Height, bounds.Width, bounds.Height)
            # Use Y inversion for pivot
            pivot_pt = rg.Point3d(param.Attributes.Pivot.X, param.Attributes.Pivot.Y * -1, 0)

        param_info = {
            "instanceGuid": guid_str,
            "parentInstanceGuid": parent_guid_str,
            "bounds": bounds_rect,
            "pivot": pivot_pt,
            "name": param.Name,
            "nickName": nick_name,
            "category": param.Category if hasattr(param, "Category") else None,
            "subCategory": param.SubCategory if hasattr(param, "SubCategory") else None,
            "description": param.Description,
            "kind": "parameter", # Identify type simply
            "sources": sources_list, # Already calculated
            "targets": targets_list, # Already calculated
            "isSelected": is_selected,
            "isInput": is_input, # Indicate if it's an input/output of a component
            # Properties specific to IGH_Param (use get_access_string for consistency)
            "access": get_access_string(param.Access) if hasattr(param, 'Access') else None,
            "optional": param.Optional if hasattr(param, 'Optional') else None,
            # Properties potentially available on component params
            "dataMapping": str(param.DataMapping) if hasattr(param, 'DataMapping') else None, # Added back from old structure
            "dataType": str(param.TypeName) if hasattr(param, 'TypeName') else None, # Added back from old structure
            "simplify": param.Simplify if hasattr(param, 'Simplify') else None, # Added back from old structure (usually boolean)
        }

        # Add specific input parameter properties like old structure
        if is_input:
            try:
                hint = param.TypeHint
                param_info["dataTypeHint"] = str(hint.TypeName) if hint else None
            except Exception:
                param_info["dataTypeHint"] = "N/A"

        # Specific handling for standalone params like sliders/panels (even in detailed mode)
        if not parent_guid_str:
            if isinstance(param, Grasshopper.Kernel.Special.GH_NumberSlider):
                param_info["kind"] = "slider"
                try:
                    param_info["slider"] = {
                        "min": float(param.Slider.Minimum),
                        "max": float(param.Slider.Maximum),
                        "value": float(param.Slider.Value),
                        "decimals": int(param.Slider.DecimalPlaces),
                        "type": str(param.Slider.Type)
                    }
                except: pass # Ignore errors getting slider details
            elif isinstance(param, Grasshopper.Kernel.Special.GH_Panel):
                param_info["kind"] = "panel"
                try:
                    param_info["panelContent"] = param.UserText
                except: pass

        return param_info

    except Exception as e:
        # Log error simply, don't wrap everything in try/except
        error_msg = "Error getting detailed param info for {}: {}".format(guid_str, e)
        # Use sticky for persistent logging accessible by main thread
        existing_error = sc.sticky.get("processing_error", "")
        sc.sticky["processing_error"] = (existing_error + "\n" + error_msg).strip()
        return None # Return None on failure


def get_component_info(comp, is_selected=False, simplified=False):
    """Collect detailed information from a Grasshopper component.
       Based on GHCodeMCP_old_working.py structure, with Y-inversion and selected flag.
       Includes a simplified mode.
    """
    guid_str = str(comp.InstanceGuid)
    nick_name = comp.NickName or comp.Name # Prefer NickName

    # Initialize with defaults
    bounds_rect = {}
    pivot_pt = {}
    aggregated_sources = set()
    aggregated_targets = set()
    runtime_messages = []
    param_guids = set() # Used for filtering aggregated sources/targets

    try:
        # Component Kind
        kind = str(comp.Kind) if hasattr(comp, 'Kind') else str(comp.__class__.__name__)

        # --- Calculate pivot, runtime messages, aggregated sources/targets for both modes ---
        if hasattr(comp, "Attributes") and comp.Attributes:
            # Use Y inversion for pivot
            pivot_pt = rg.Point3d(comp.Attributes.Pivot.X, comp.Attributes.Pivot.Y * -1, 0)

        try:
            messages =  comp.RuntimeMessages(comp.RuntimeMessageLevel) # Get warnings and errors
            runtime_messages = [str(m) for m in messages] if messages else []
        except:
            pass # Keep empty list on error

        # Aggregate sources/targets from component parameters
        if hasattr(comp, "Params"):
            if hasattr(comp.Params, "Input"):
                for p in comp.Params.Input:
                    p_guid = str(p.InstanceGuid)
                    param_guids.add(p_guid)
                    # Need sources from the parameter itself to aggregate
                    param_info_temp = get_param_info(p, is_input=True, parent_instance_guid=comp.InstanceGuid, simplified=True) # Use simplified=True here for efficiency
                    if param_info_temp:
                         aggregated_sources.update(param_info_temp.get("sources", []))
            if hasattr(comp.Params, "Output"):
                for p in comp.Params.Output:
                    p_guid = str(p.InstanceGuid)
                    param_guids.add(p_guid)
                    param_info_temp = get_param_info(p, is_input=False, parent_instance_guid=comp.InstanceGuid, simplified=True) # Use simplified=True here for efficiency
                    if param_info_temp:
                         aggregated_targets.update(param_info_temp.get("targets", []))

        # Filter out the component's own parameters' GUIDs and itself
        final_sources = list(s for s in aggregated_sources if s != guid_str and s not in param_guids)
        final_targets = list(t for t in aggregated_targets if t != guid_str and t not in param_guids)


        if simplified:
            # Return minimal info focusing on identity, connectivity, and status
            info = {
                "instanceGuid": guid_str,
                "name": comp.Name,
                "nickName": nick_name,
                "description": comp.Description,
                "kind": kind,
                "pivot": pivot_pt, # Include simplified pivot
                "sources": final_sources,
                "targets": final_targets,
                "isSelected": is_selected,
                "runtimeMessages": runtime_messages # Include runtime messages
            }
            return info

        # --- Detailed Component Information ---
        if hasattr(comp, "Attributes") and comp.Attributes:
            bounds = comp.Attributes.Bounds
            # Use Y inversion
            bounds_rect = RectangleF(bounds.X, (bounds.Y * -1) - bounds.Height, bounds.Width, bounds.Height)

        comp_info = {
            "instanceGuid": guid_str,
            "name": comp.Name,
            "nickName": nick_name,
            "description": comp.Description,
            "category": comp.Category if hasattr(comp, "Category") else None,
            "subCategory": comp.SubCategory if hasattr(comp, "SubCategory") else None,
            "kind": kind,
            "bounds": bounds_rect, # Detailed bounds
            "pivot": pivot_pt, # Already calculated
            "isSelected": is_selected,
            "computationTime": float(comp.ProcessorTime.Milliseconds) if hasattr(comp, "ProcessorTime") else 0.0,
            "runtimeMessages": runtime_messages, # Already calculated
            "Inputs": [], # Use "Inputs"/"Outputs" like old script for compatibility? -> Yes
            "Outputs": [],
            "sources": final_sources, # Already calculated
            "targets": final_targets, # Already calculated
        }

        # Script Component Specific Info (adapted from GHCodeMCP.py)
        if hasattr(comp, "Code"): # Good indicator for script components
            comp_info["isScriptComponent"] = True
            comp_info["Code"] = comp.Code # Keep code retrieval
            # Check if code is referenced from file
            comp_info["codeReferenceFromFile"] = False
            comp_info["codeReferencePath"] = None
            if hasattr(comp, "InputIsPath"):
                comp_info["codeReferenceFromFile"] = comp.InputIsPath
                if comp.InputIsPath and hasattr(comp, "Params") and hasattr(comp.Params, "Input"):
                    try:
                        # Find the 'code' input parameter
                        code_param = next((p for p in comp.Params.Input if (p.NickName or p.Name).lower() == "code"), None)
                        if code_param and code_param.VolatileDataCount > 0:
                             # Assuming the path is the first item in the data tree
                             path_data = code_param.VolatileData.get_Branch(0)
                             if path_data and len(path_data) > 0:
                                comp_info["codeReferencePath"] = str(path_data[0]) # Use NickName or Name
                    except Exception as e_path:
                         error_msg = "Error getting script path for {}: {}".format(guid_str, e_path)
                         existing_error = sc.sticky.get("processing_error", "")
                         sc.sticky["processing_error"] = (existing_error + "\n" + error_msg).strip()


        # Get detailed input and output parameter info (only in detailed mode)
        if hasattr(comp, "Params"):
            if hasattr(comp.Params, "Input"):
                for p in comp.Params.Input:
                    # Call get_param_info with simplified=False for detailed output
                    param_info = get_param_info(p, is_input=True, parent_instance_guid=comp.InstanceGuid, is_selected=False, simplified=False)
                    if param_info:
                         comp_info["Inputs"].append(param_info)
            if hasattr(comp.Params, "Output"):
                for p in comp.Params.Output:
                    param_info = get_param_info(p, is_input=False, parent_instance_guid=comp.InstanceGuid, is_selected=False, simplified=False)
                    if param_info:
                         comp_info["Outputs"].append(param_info)

        return comp_info

    except Exception as e:
        error_msg = "Error getting component info for {}: {}".format(guid_str, e)
        existing_error = sc.sticky.get("processing_error", "")
        sc.sticky["processing_error"] = (existing_error + "\n" + error_msg).strip()
        return None

# --- Object Retrieval Functions (Simplified approach based on GHCodeMCP_old_working.py context gathering) ---

def expire_grasshopper_component(doc, instance_guid_str):
    """Expire a Grasshopper component by GUID and return its information."""
    if not doc: return {"status": "error", "result": "No document provided"}
    try:
        target_guid = System.Guid(instance_guid_str)
        # Use FindObject directly for efficiency
        obj = doc.FindObject(target_guid, True) # True includes nested objects if applicable
        if not obj:
            return {"status": "error", "result": "Object not found with GUID: " + instance_guid_str}
            
        obj.ExpireSolution(True)
        
        # Get component info after expiring
        if isinstance(obj, Grasshopper.Kernel.IGH_Component):
            return {"status": "success", "result": get_component_info(obj)}
        elif isinstance(obj, Grasshopper.Kernel.IGH_Param):
            return {"status": "success", "result": get_param_info(obj, is_input=False)}
        return {"status": "success", "result": {"message": "Component expired but not a component or param"}}
    
    except Exception as e:
        # Log error finding object
        error_msg = "Error finding object by GUID {}: {}".format(instance_guid_str, e)
        existing_error = sc.sticky.get("processing_error", "")
        sc.sticky["processing_error"] = (existing_error + "\n" + error_msg).strip()
        return {"status": "error", "result": error_msg}



def get_all_relevant_objects_info(doc, selected_guids_set=None, simplified=False):
    """
    Collects info for all components and standalone parameters in the document.
    Returns a dictionary keyed by instance GUID. Marks selection status.
    Includes a simplified mode.
    """
    graph = {}
    if selected_guids_set is None:
        selected_guids_set = set()

    # Collect info for all components and standalone params
    for obj in doc.Objects:
        if not hasattr(obj, "InstanceGuid"): continue
        guid_str = str(obj.InstanceGuid)
        is_selected = guid_str in selected_guids_set
        info = None

        if isinstance(obj, Grasshopper.Kernel.IGH_Component):
            info = get_component_info(obj, is_selected=is_selected, simplified=simplified)
        elif isinstance(obj, Grasshopper.Kernel.IGH_Param):
            # Only include standalone parameters at the top level
            parent_comp = obj.Attributes.Parent if hasattr(obj, "Attributes") and obj.Attributes else None
            if not parent_comp:
                # Use get_param_info directly for standalone params
                info = get_param_info(obj, is_input=False, parent_instance_guid=None, is_selected=is_selected, simplified=simplified)

        if info:
            graph[guid_str] = info

    return graph


def get_objects_with_context(target_guids, context_depth=0, simplified=False):
    """
    Get info for target objects and their context (neighbors).
    Focuses on components and standalone parameters.
    Returns a dictionary keyed by instance GUID.
    Includes a simplified mode.
    """
    doc = ghenv.Component.OnPingDocument()
    if not doc:
        sc.sticky["processing_error"] = "get_objects_with_context: No active Grasshopper document."
        return {}

    target_guids_set = set(str(g) for g in target_guids)

    # 1. Get info for *all* relevant objects first, passing simplified flag
    all_objects_info = get_all_relevant_objects_info(doc, selected_guids_set=target_guids_set, simplified=simplified)

    # 2. Identify the initial set of objects to include (the targets)
    result_graph = {}
    guids_to_include = set()

    for guid_str in target_guids_set:
        if guid_str in all_objects_info:
            guids_to_include.add(guid_str)
            # Ensure the directly targeted item is marked as selected *in the final result*
            # The 'is_selected' flag is already set correctly by get_all_relevant_objects_info
        else:
            # If the target GUID itself isn't a component or standalone param,
            # check if it's a child parameter and add its parent instead.
            obj = get_object_by_instance_guid(doc, guid_str) # Helper function assumed to exist or be added
            if obj and isinstance(obj, IGH_Param):
                 parent_comp = obj.Attributes.Parent if hasattr(obj, "Attributes") and obj.Attributes else None
                 if parent_comp and hasattr(parent_comp, "InstanceGuid"):
                     parent_guid_str = str(parent_comp.InstanceGuid)
                     if parent_guid_str in all_objects_info:
                         guids_to_include.add(parent_guid_str)
                         # Mark the parent as selected if its child was targeted
                         # Check if it's already selected; if not, mark it
                         if not all_objects_info[parent_guid_str].get('isSelected', False):
                              all_objects_info[parent_guid_str]['isSelected'] = True


    # 3. Perform Context Traversal (simple neighbor finding using info from all_objects_info)
    if context_depth > 0 and guids_to_include:
        max_depth = min(int(context_depth), 3) # Limit depth
        current_level = set(guids_to_include) # Start with the core items
        visited_for_context = set(guids_to_include)

        for _ in range(max_depth):
            next_level = set()
            for guid in current_level:
                if guid not in all_objects_info: continue # Skip if info wasn't collected (shouldn't happen often)

                node_info = all_objects_info[guid]
                # Sources and Targets should exist even in simplified mode
                neighbors = set(node_info.get("sources", [])) | set(node_info.get("targets", []))

                for neighbor_guid in neighbors:
                    if neighbor_guid in all_objects_info and neighbor_guid not in visited_for_context:
                        # Check if the neighbor is a component or standalone param (already filtered by all_objects_info)
                        next_level.add(neighbor_guid)
                        visited_for_context.add(neighbor_guid)
                        guids_to_include.add(neighbor_guid) # Add context GUID to the final set

            if not next_level: break # No new neighbors found
            current_level = next_level

    # 4. Build the final result graph containing only the included GUIDs
    for guid_str in guids_to_include:
        if guid_str in all_objects_info:
            result_graph[guid_str] = all_objects_info[guid_str]

    # We are omitting the explicit topological sort for simplicity,
    # relying on the order Grasshopper presents objects or the dictionary order.
    return result_graph

def get_selected_objects(context_depth=0, simplified=False):
    """
    Get currently selected objects in the Grasshopper document with context.
    Returns dictionary: {"status": "...", "result": ...}
    Includes a simplified mode.
    """
    doc = ghenv.Component.OnPingDocument()
    if not doc:
        sc.sticky["processing_error"] = "get_selected_objects: No active Grasshopper document."
        return {"status": "error", "result": "No active Grasshopper document."}

    selected_guids = []
    for obj in doc.Objects:
        is_selected = False
        if hasattr(obj, "Attributes") and obj.Attributes and hasattr(obj.Attributes, "Selected"):
            is_selected = obj.Attributes.Selected
        if is_selected and hasattr(obj, "InstanceGuid"):
            selected_guids.append(str(obj.InstanceGuid))

    if not selected_guids:
        return {"status": "success", "result": {}} # No objects selected

    try:
        # Use the context retrieval function, passing simplified flag
        objects_dict = get_objects_with_context(selected_guids, context_depth=context_depth, simplified=simplified)
        return {"status": "success", "result": objects_dict}
    except Exception as e:
        error_msg = "Error getting selected objects: {}".format(e)
        existing_error = sc.sticky.get("processing_error", "")
        sc.sticky["processing_error"] = (existing_error + "\n" + error_msg).strip()
        return {"status": "error", "result": error_msg}


def get_grasshopper_context(simplified=False):
    """
    Get information about *all* components and *standalone* parameters in the document.
    Returns dictionary: {"status": "...", "result": ...}
    Includes a simplified mode.
    """
    doc = ghenv.Component.OnPingDocument()
    if not doc:
        sc.sticky["processing_error"] = "get_grasshopper_context: No active Grasshopper document."
        return {"status": "error", "result": "No active Grasshopper document."}

    try:
        # Use the core info gathering function, passing simplified flag
        # It determines selection status internally based on the document state.
        all_info = get_all_relevant_objects_info(doc, simplified=simplified)
        return {"status": "success", "result": all_info}
    except Exception as e:
        error_msg = "Error getting full context: {}".format(e)
        existing_error = sc.sticky.get("processing_error", "")
        sc.sticky["processing_error"] = (existing_error + "\n" + error_msg).strip()
        return {"status": "error", "result": error_msg}


# --- Component Update Functions (Using UI Thread Marshalling from GHCodeMCP.py) ---

def _update_script_component_on_ui_thread(instance_guid_str, code, description, message_to_user, param_definitions):
    """
    Core logic to update script component, MUST run on UI thread.
    Based on GHCodeMCP.py's implementation for stability.
    """
    result = {"status": "error", "result": "Update failed (UI thread)."}
    comp = None
    doc = ghenv.Component.OnPingDocument()
    if not doc:
        return {"status": "error", "result": "No active Grasshopper document (UI thread)."}

    try:
        target_instance_guid = Guid.Parse(instance_guid_str)
    except Exception as guid_e:
        return {"status": "error", "result": "Invalid instance GUID format: {}.".format(guid_e)}

    comp = doc.FindObject(target_instance_guid, False)
    # Check if it's a script component (has Code attribute is a good proxy)
    if not comp or not hasattr(comp, "Code"):
         return {"status": "error", "result": "Target component (GUID: {}) not found or is not a script component.".format(instance_guid_str)}

    # --- Connection Restoration Setup ---
    old_input_connections = {} # { nickName: [source_guid_obj1, ...], ... }
    old_output_connections = {} # { nickName: [recipient_param_obj1, ...], ... }
    connection_restore_log = []

    # === Step 0: Record Existing Connections BEFORE modifications ===
    try:
        if hasattr(comp.Params, "Input"):
            for p_in in list(comp.Params.Input):
                key = p_in.NickName or p_in.Name # Use NickName first
                if key and p_in.Sources:
                    old_input_connections[key] = [src for src in p_in.Sources if src]
        if hasattr(comp.Params, "Output"):
             for p_out in list(comp.Params.Output):
                 key = p_out.NickName or p_out.Name # Use NickName first
                 if key and p_out.Recipients:
                     old_output_connections[key] = [rec for rec in p_out.Recipients if rec]
        connection_restore_log.append("Recorded {} input and {} output connection sets.".format(len(old_input_connections), len(old_output_connections)))
    except Exception as e_rec:
        connection_restore_log.append("Warning: Error recording connections: {}".format(e_rec))
        old_input_connections = {}
        old_output_connections = {}

    # --- Perform Updates ---
    code_updated = False
    params_updated = False
    description_updated = False
    message_set = False
    canvas = gh.Instances.ActiveCanvas
    if canvas: canvas.Document.Enabled = False # Freeze canvas

    # Store newly created parameter objects for connection restoration
    new_input_params = {} # Use dict {nickName: param_obj} for easier lookup
    new_output_params = {} # Use dict {nickName: param_obj}

    try:
        # === Step 1: Update Parameters (if definitions provided) ===
        if param_definitions is not None:
            dummy_input = None
            dummy_output = None
            try:
                # --- Dummy Parameter Strategy ---
                dummy_input_def = {"name": "__dummy_in__", "nickName": "__dummy_in__", "description": "Temp"}
                dummy_output_def = {"name": "__dummy_out__", "nickName": "__dummy_out__", "description": "Temp"}
                dummy_input = create_gh_input_param(dummy_input_def)
                dummy_output = create_gh_output_param(dummy_output_def)
                comp.Params.RegisterInputParam(dummy_input)
                comp.Params.RegisterOutputParam(dummy_output)

                # --- Remove Old Parameters ---
                inputs_to_remove = [p for p in comp.Params.Input if p.InstanceGuid != dummy_input.InstanceGuid]
                outputs_to_remove = [p for p in comp.Params.Output if p.InstanceGuid != dummy_output.InstanceGuid]
                for p in inputs_to_remove: comp.Params.UnregisterInputParameter(p)
                for p in outputs_to_remove: comp.Params.UnregisterOutputParameter(p)

                # --- Add New Parameters ---
                default_description = "Dynamically added parameter"
                for p_def in param_definitions:
                    param_type = p_def.get("type", "").lower()
                    if param_type == "input":
                        new_param = create_gh_input_param(p_def, default_description)
                        comp.Params.RegisterInputParam(new_param)
                        new_input_params[new_param.NickName or new_param.Name] = new_param
                    elif param_type == "output":
                        new_param = create_gh_output_param(p_def, default_description)
                        comp.Params.RegisterOutputParam(new_param)
                        new_output_params[new_param.NickName or new_param.Name] = new_param

                # --- Ensure Default Output 'output' ---
                current_output_nicknames = set(p.NickName or p.Name for p in comp.Params.Output)
                if "output" not in current_output_nicknames and "__dummy_out__" not in current_output_nicknames:
                     default_out_def = {"name": "output", "nickName": "output", "description": "Default output"}
                     default_out = create_gh_output_param(default_out_def)
                     comp.Params.RegisterOutputParam(default_out)
                     new_output_params[default_out.NickName or default_out.Name] = default_out

                # --- Remove Dummies ---
                if dummy_input and dummy_input in list(comp.Params.Input): comp.Params.UnregisterInputParameter(dummy_input)
                if dummy_output and dummy_output in list(comp.Params.Output): comp.Params.UnregisterOutputParameter(dummy_output)

                params_updated = True
                comp.Params.OnParametersChanged()
                comp.ClearData()

            except Exception as e_param:
                 result = {"status": "error", "result": "Error updating parameters: {}".format(e_param)}
                 try: # Cleanup dummies on error
                      if dummy_input and dummy_input in list(comp.Params.Input): comp.Params.UnregisterInputParameter(dummy_input)
                      if dummy_output and dummy_output in list(comp.Params.Output): comp.Params.UnregisterOutputParameter(dummy_output)
                 except: pass
                 raise # Re-raise to be caught by outer try/finally

        # === Step 2: Restore Connections (if params were updated) ===
        if params_updated:
            connection_restore_log.append("Attempting connection restoration...")
            # Restore Input Connections
            for nick_name, new_p_in in new_input_params.items():
                if nick_name in old_input_connections:
                    sources_to_connect = old_input_connections[nick_name]
                    sources_found = 0
                    for source_param in sources_to_connect:
                        if source_param and isinstance(source_param, IGH_Param) and source_param.InstanceGuid != System.Guid.Empty:
                             try:
                                 new_p_in.AddSource(source_param)
                                 sources_found += 1
                             except Exception as conn_e_in:
                                 connection_restore_log.append(" Error connecting Input '{}' to Source {}: {}".format(nick_name, source_param.InstanceGuid, conn_e_in))
                    if sources_found > 0:
                         connection_restore_log.append(" Restored {} source(s) for Input '{}'".format(sources_found, nick_name))

            # Restore Output Connections
            for nick_name, new_p_out in new_output_params.items():
                if nick_name in old_output_connections:
                    recipients_to_connect = old_output_connections[nick_name]
                    recipients_found = 0
                    for recipient_param in recipients_to_connect:
                        if recipient_param and isinstance(recipient_param, IGH_Param) and recipient_param.InstanceGuid != System.Guid.Empty:
                             try:
                                 recipient_param.AddSource(new_p_out) # Connect recipient TO new output
                                 recipients_found += 1
                             except Exception as conn_e_out:
                                 connection_restore_log.append(" Error connecting Output '{}' to Recipient {}: {}".format(nick_name, recipient_param.InstanceGuid, conn_e_out))
                    if recipients_found > 0:
                         connection_restore_log.append(" Restored {} recipient(s) for Output '{}'".format(recipients_found, nick_name))

        # === Step 3: Update Code, Description, Message ===
        if code is not None:
            comp.Code = str(code) # Ensure it's a string
            code_updated = True

        if description is not None:
            comp.Description = str(description) # Ensure it's a string
            description_updated = True

        # Set message_to_user on the 'output' parameter if it exists and message is provided
        if message_to_user is not None:
             output_param = next((p for p in comp.Params.Output if (p.NickName or p.Name) == "output"), None)
             if output_param:
                 output_param.ClearData()
                 output_param.AddVolatileData(Grasshopper.Kernel.Data.GH_Path(0), 0, str(message_to_user))
                 message_set = True
             else:
                 connection_restore_log.append("Warning: 'output' parameter not found to set message.")

        # === Step 4: Finalize layout and solution expiry ===
        if hasattr(comp, "Attributes"): comp.Attributes.ExpireLayout()
        comp.ExpireSolution(True) # Expire downstream

        result = {
            "status": "success",
            "result": {
                "code_updated": code_updated,
                "params_updated": params_updated,
                "description_updated": description_updated,
                "message_set": message_set,
                "component_type": type(comp).__name__,
                "connection_log": connection_restore_log # Include log
            }
        }

    except Exception as e_main:
        # Catch errors from any step
        tb_str = traceback.format_exc()
        error_msg = "Error during component update: {}".format(e_main)
        result = {"status": "error", "result": error_msg}
        # Store detailed error in sticky for component bubble display
        sc.sticky["last_update_error"] = "Update Error ({}): {}\n{}".format(instance_guid_str, e_main, tb_str)
        sc.sticky["connection_log"] = "\n".join(connection_restore_log + ["ERROR: " + tb_str])

    finally:
        # === CRITICAL: Always re-enable canvas and refresh ===
        if canvas: canvas.Document.Enabled = True
        if comp and hasattr(comp, "Attributes"): comp.Attributes.ExpireLayout() # Expire again
        if canvas: canvas.Refresh() # Refresh canvas

    return result


def update_script_component(instance_guid, code=None, description=None, message_to_user=None, param_definitions=None):
    """ Updates a script component safely using the UI thread. """
    sc.sticky.pop("last_update_error", None) # Clear previous specific update error
    sc.sticky.pop("connection_log", None) # Clear previous connection log

    action = Action(lambda:
        sc.sticky.update({"__temp_result":
            _update_script_component_on_ui_thread(instance_guid, code, description, message_to_user, param_definitions)
        })
    )
    Rhino.RhinoApp.InvokeOnUiThread(action)
    result = sc.sticky.pop("__temp_result", {"status": "error", "result": "UI thread action failed to execute."})

    # Add logged error/log to result if necessary
    last_err = sc.sticky.get("last_update_error")
    conn_log = sc.sticky.get("connection_log")
    if last_err and result.get("status") == "error":
        result["result"] = "{}; Logged Error: {}".format(result.get("result", "Update error"), last_err)
    elif last_err:
        result["warning"] = "Update may have succeeded with issues: {}".format(last_err)
    if conn_log and isinstance(result.get("result"), dict):
        result["result"]["connection_log"] = conn_log.splitlines()

    return result

# --- Update Script with Code Reference (UI Thread Safe) ---
def _update_script_with_code_ref_on_ui_thread(instance_guid_str, file_path, param_definitions, description, name, force_code_reference):
    """ Core logic to update script component for code reference, MUST run on UI thread. """
    result = {"status": "error", "result": "Code reference update failed (UI thread)."}
    comp = None
    doc = ghenv.Component.OnPingDocument()
    if not doc:
        return {"status": "error", "result": "No active Grasshopper document (UI thread)."}

    try:
        target_instance_guid = Guid.Parse(instance_guid_str)
    except Exception as guid_e:
        return {"status": "error", "result": "Invalid instance GUID format: {}.".format(guid_e)}

    comp = doc.FindObject(target_instance_guid, False)
    if not comp:
         return {"status": "error", "result": "Component not found (GUID: {}).".format(instance_guid_str)}
    # Check if it's a script component supporting InputIsPath
    if not hasattr(comp, "Code") or not hasattr(comp, "InputIsPath"):
        return {"status": "error", "result": "Component (GUID: {}) is not a script component supporting code reference.".format(instance_guid_str)}

    # --- Connection Restoration Setup ---
    old_input_connections = {}
    old_output_connections = {}
    connection_restore_log = ["Code Ref Update Log:"]

    # === Step 0: Record Connections ===
    try:
        if hasattr(comp.Params, "Input"):
            for p_in in list(comp.Params.Input):
                key = p_in.NickName or p_in.Name
                if key and p_in.Sources: old_input_connections[key] = [src for src in p_in.Sources if src]
        if hasattr(comp.Params, "Output"):
             for p_out in list(comp.Params.Output):
                 key = p_out.NickName or p_out.Name
                 if key and p_out.Recipients: old_output_connections[key] = [rec for rec in p_out.Recipients if rec]
        connection_restore_log.append(" Recorded {} input/{} output sets.".format(len(old_input_connections), len(old_output_connections)))
    except Exception as e_rec:
        connection_restore_log.append("Warning: Error recording connections: {}".format(e_rec))
        old_input_connections = {}
        old_output_connections = {}

    # --- Perform Updates ---
    code_ref_mode_set = False # Track if InputIsPath was set
    file_path_set = False
    params_updated = False
    desc_updated = False
    name_updated = False
    canvas = gh.Instances.ActiveCanvas
    if canvas: canvas.Document.Enabled = False # Freeze canvas

    new_input_params = {} # {nickName: param_obj}
    new_output_params = {} # {nickName: param_obj}
    code_param_ref = None # Reference to the 'code' parameter

    try:
        # === Step 1: Ensure Code Reference Mode and Find/Create 'code' Param ===
        # Find the 'code' parameter first
        code_param_ref = next((p for p in comp.Params.Input if (p.NickName or p.Name).lower() == "code"), None)

        # If forcing or file_path is provided, ensure InputIsPath=True and 'code' param exists
        if force_code_reference or file_path is not None:
            if not comp.InputIsPath:
                connection_restore_log.append(" Setting InputIsPath = True")
                comp.InputIsPath = True
                code_ref_mode_set = True # Mark that we changed the mode

            if not code_param_ref:
                 connection_restore_log.append(" 'code' param not found, attempting creation.")
                 if hasattr(comp, "ConstructCodeInputParameter"):
                      try:
                          code_param_ref = comp.ConstructCodeInputParameter()
                          code_param_ref.NickName = "code"
                          code_param_ref.Name = "code"
                          code_param_ref.Description = "Path to Python code file"
                          comp.Params.RegisterInputParam(code_param_ref)
                          connection_restore_log.append(" Registered new 'code' param.")
                          # Need to expire layout if we added a param here
                          if hasattr(comp, "Attributes"): comp.Attributes.ExpireLayout()
                      except Exception as e_create_code:
                          connection_restore_log.append(" Error creating 'code' param: {}".format(e_create_code))
                          code_param_ref = None # Ensure it's None if creation failed
                 else:
                      connection_restore_log.append(" Warning: Component cannot construct 'code' param automatically.")

            # If mode was just set or we forced, expire solution early
            # to help GH recognize the InputIsPath change before param modifications
            if code_ref_mode_set or force_code_reference:
                comp.ExpireSolution(True)
                time.sleep(0.05) # Small pause might help GH internals catch up


        # === Step 2: Update Parameters (if definitions provided, preserving 'code') ===
        if param_definitions is not None:
            dummy_input = None
            dummy_output = None
            try:
                # --- Dummy Strategy ---
                dummy_input_def = {"name": "__dummy_in_ref__", "nickName": "__dummy_in_ref__", "description": "TempRef"}
                dummy_output_def = {"name": "__dummy_out_ref__", "nickName": "__dummy_out_ref__", "description": "TempRef"}
                dummy_input = create_gh_input_param(dummy_input_def)
                dummy_output = create_gh_output_param(dummy_output_def)
                comp.Params.RegisterInputParam(dummy_input)
                comp.Params.RegisterOutputParam(dummy_output)

                # --- Identify 'code' param GUID to preserve ---
                code_param_guid = None
                if not code_param_ref: # Find it if not already referenced
                     code_param_ref = next((p for p in comp.Params.Input if (p.NickName or p.Name).lower() == "code"), None)
                if code_param_ref:
                    code_param_guid = code_param_ref.InstanceGuid

                # --- Remove Old (except 'code' and dummies) ---
                inputs_to_remove = [p for p in comp.Params.Input if p.InstanceGuid != dummy_input.InstanceGuid and p.InstanceGuid != code_param_guid]
                outputs_to_remove = [p for p in comp.Params.Output if p.InstanceGuid != dummy_output.InstanceGuid]
                for p in inputs_to_remove: comp.Params.UnregisterInputParameter(p)
                for p in outputs_to_remove: comp.Params.UnregisterOutputParameter(p)

                # --- Add New (skip 'code' explicitly) ---
                default_description = "Dynamically added parameter"
                for p_def in param_definitions:
                    param_type = p_def.get("type", "").lower()
                    # Check NickName first, then Name for 'code' match
                    param_id = p_def.get("nickName", p_def.get("name", "")).lower()
                    if param_id == "code":
                        connection_restore_log.append(" Skipped adding explicit 'code' param from definition.")
                        continue # Skip 'code' definition

                    if param_type == "input":
                        new_param = create_gh_input_param(p_def, default_description)
                        comp.Params.RegisterInputParam(new_param)
                        new_input_params[new_param.NickName or new_param.Name] = new_param
                    elif param_type == "output":
                        new_param = create_gh_output_param(p_def, default_description)
                        comp.Params.RegisterOutputParam(new_param)
                        new_output_params[new_param.NickName or new_param.Name] = new_param

                # --- Ensure Default Output 'output' ---
                current_output_nicknames = set(p.NickName or p.Name for p in comp.Params.Output)
                if "output" not in current_output_nicknames and "__dummy_out_ref__" not in current_output_nicknames:
                     default_out_def = {"name": "output", "nickName": "output", "description": "Default output"}
                     default_out = create_gh_output_param(default_out_def)
                     comp.Params.RegisterOutputParam(default_out)
                     new_output_params[default_out.NickName or default_out.Name] = default_out

                # --- Remove Dummies ---
                if dummy_input and dummy_input in list(comp.Params.Input): comp.Params.UnregisterInputParameter(dummy_input)
                if dummy_output and dummy_output in list(comp.Params.Output): comp.Params.UnregisterOutputParameter(dummy_output)

                params_updated = True
                comp.Params.OnParametersChanged()
                comp.ClearData() # Clear data after param changes

            except Exception as e_param_ref:
                 connection_restore_log.append(" Error updating parameters during code ref update: {}".format(e_param_ref))
                 try: # Cleanup dummies
                      if dummy_input and dummy_input in list(comp.Params.Input): comp.Params.UnregisterInputParameter(dummy_input)
                      if dummy_output and dummy_output in list(comp.Params.Output): comp.Params.UnregisterOutputParameter(dummy_output)
                 except: pass
                 # Don't re-raise, try other updates

        # === Step 3: Restore Connections (if params updated) ===
        if params_updated:
            connection_restore_log.append(" Attempting connection restoration (code ref)...")
            # Restore Inputs (excluding 'code' param)
            for nick_name, new_p_in in new_input_params.items():
                if nick_name in old_input_connections:
                    sources = old_input_connections[nick_name]
                    restored_count = 0
                    for src in sources:
                         if src and isinstance(src, IGH_Param) and src.InstanceGuid != Guid.Empty:
                             try: new_p_in.AddSource(src); restored_count += 1
                             except Exception as cie: connection_restore_log.append(" Error IN {}->{}:{}".format(src.InstanceGuid,nick_name,cie))
                    if restored_count > 0: connection_restore_log.append(" Restored {} src for {}".format(restored_count, nick_name))
            # Restore Outputs
            for nick_name, new_p_out in new_output_params.items():
                 if nick_name in old_output_connections:
                     recipients = old_output_connections[nick_name]
                     restored_count = 0
                     for rec in recipients:
                          if rec and isinstance(rec, IGH_Param) and rec.InstanceGuid != Guid.Empty:
                              try: rec.AddSource(new_p_out); restored_count += 1
                              except Exception as coe: connection_restore_log.append(" Error OUT {}->{}:{}".format(nick_name,rec.InstanceGuid,coe))
                     if restored_count > 0: connection_restore_log.append(" Restored {} rec for {}".format(restored_count, nick_name))


        # === Step 4: Update Description and Name ===
        if description is not None:
            comp.Description = str(description)
            desc_updated = True
        if name is not None:
            comp.NickName = str(name) # Update NickName
            name_updated = True

        # === Step 5: CRITICAL - Set File Path on 'code' Param (if needed) ===
        # Do this *after* all other param manipulations and *before* final expire
        if file_path is not None:
            if not code_param_ref: # Find 'code' param again if it wasn't found/created earlier
                 code_param_ref = next((p for p in comp.Params.Input if (p.NickName or p.Name).lower() == "code"), None)

            if code_param_ref:
                 try:
                      # Ensure the component is in the right mode *before* setting path
                      if not comp.InputIsPath:
                          connection_restore_log.append(" Setting InputIsPath = True (before final path set)")
                          comp.InputIsPath = True
                          # Expire here? Maybe not, do it at the end.

                      connection_restore_log.append(" Setting VolatileData for 'code' param: '{}'".format(file_path))
                      #code_param_ref.ClearPersistentData() # Clear any persistent path first
                      # Clear volatile data too, just in case
                      code_param_ref.ClearData()
                      code_param_ref.AddVolatileData(Grasshopper.Kernel.Data.GH_Path(0), 0, str(file_path))
                      file_path_set = True # Mark as set
                 except Exception as e_path_set:
                      connection_restore_log.append(" Error setting final file path: {}".format(e_path_set))
                      file_path_set = False
            else:
                 connection_restore_log.append(" Warning: 'code' param not found for final path setting.")
                 file_path_set = False


        # === Step 6: Finalize layout and solution expiry ===
        # Ensure layout is updated *after* all potential param changes & path setting
        if hasattr(comp, "Attributes"): comp.Attributes.ExpireLayout()
        # Expire solution *after* setting the volatile path data
        comp.ExpireSolution(True)
     

        result = {
            "status": "success",
            "result": {
                # "code_reference_enforced": code_ref_enforced, # Removed this confusing flag
                "code_reference_mode_set": code_ref_mode_set, # Indicate if InputIsPath was changed
                "file_path_set": file_path_set,
                "params_updated": params_updated,
                "description_updated": desc_updated,
                "name_updated": name_updated,
                "connection_log": connection_restore_log # Include full log
            }
        }

    except Exception as e_main_ref:
        tb_str = traceback.format_exc()
        error_msg = "Error during code reference update: {}".format(e_main_ref)
        result = {"status": "error", "result": error_msg}
        sc.sticky["last_update_error"] = "Code Ref Update Error ({}): {}\n{}".format(instance_guid_str, e_main_ref, tb_str)
        sc.sticky["connection_log"] = "\n".join(connection_restore_log + ["ERROR: " + tb_str])

    finally:
        # === CRITICAL: Always re-enable canvas and refresh ===
        if canvas: canvas.Document.Enabled = True
        if comp and hasattr(comp, "Attributes"): 
            comp.Attributes.ExpireLayout() # Expire again
            comp.ExpireSolution(True)
        if canvas: canvas.Refresh() # Refresh canvas

    return result


def update_script_with_code_reference(instance_guid, file_path=None, param_definitions=None, description=None, name=None, force_code_reference=False):
    """ Updates a script component for code reference safely using the UI thread. """
    sc.sticky.pop("last_update_error", None) # Clear previous specific update error
    sc.sticky.pop("connection_log", None) # Clear previous connection log

    action = Action(lambda:
        sc.sticky.update({"__temp_result":
            _update_script_with_code_ref_on_ui_thread(instance_guid, file_path, param_definitions, description, name, force_code_reference)
        })
    )
    Rhino.RhinoApp.InvokeOnUiThread(action)
    result = sc.sticky.pop("__temp_result", {"status": "error", "result": "UI thread action failed to execute."})
    
    # Add logged error/log to result if necessary
    last_err = sc.sticky.get("last_update_error")
    conn_log = sc.sticky.get("connection_log")
    if last_err and result.get("status") == "error":
        result["result"] = "{}; Logged Error: {}".format(result.get("result", "Update error"), last_err)
    elif last_err:
        result["warning"] = "Update may have succeeded with issues: {}".format(last_err)
    if conn_log and isinstance(result.get("result"), dict):
        # Add log lines to the result dictionary if it exists
        result["result"]["connection_log"] = conn_log.splitlines()


    return result

# --- Execute Code ---
def execute_code(code_str):
    """Executes Python code string and returns the result. Runs synchronously."""
    # Note: This executes in the context of the GHPython component.
    # Be cautious about code that might block or modify the document directly.
    try:
        local_vars = {}
        # Execute using globals() from this script's context and a dedicated local dict
        exec(code_str, globals(), local_vars)

        # Return value from 'result' variable if defined in the executed code
        if 'result' in local_vars:
            return {"status": "success", "result": local_vars['result']}
        else:
            return {"status": "success", "result": "Code executed successfully (no 'result' variable)."}
    except Exception as e:
        # Log detailed error to sticky for main thread display
        tb_str = traceback.format_exc()
        error_msg = "Error executing code: {}\n{}".format(e, tb_str)
        existing_error = sc.sticky.get("processing_error", "")
        sc.sticky["processing_error"] = (existing_error + "\n" + error_msg).strip()
        # Return simple error message to client
        return {"status": "error", "result": "Error executing code: {}".format(e)}


# --- Command Processing (Adapted from GHCodeMCP.py) ---

def parse_command(body_str):
    """Parse the incoming JSON command data."""
    # Clear previous processing error for this request
    sc.sticky.pop("processing_error", None)
    try:
        if not body_str or not body_str.strip():
             raise ValueError("Received empty request body.")
        command_data = json.loads(body_str)
        if isinstance(command_data, dict) and "type" in command_data:
            return command_data
        else:
            raise ValueError("Parsed JSON is not a valid command object with a 'type' key.")
    except ValueError as json_e: # Includes JSONDecodeError
        error_msg = "Invalid command format (not valid JSON or missing 'type'): {}. Body: '{}...'".format(json_e, body_str[:100])
        sc.sticky["processing_error"] = error_msg
        return {"type": "error", "error_message": error_msg} # Signal error to process_command
    except Exception as e:
        tb_str = traceback.format_exc()
        error_msg = "Unexpected error parsing command: {}\n{}. Body: '{}...'".format(e, tb_str, body_str[:100])
        sc.sticky["processing_error"] = error_msg
        return {"type": "error", "error_message": error_msg}


def process_command(command_data):
    """Process a command dictionary and return the result dictionary."""
    command_type = command_data.get("type", "unknown")

    # Handle parsing errors signaled by parse_command
    if command_type == "error":
        return {"status": "error", "result": command_data.get("error_message", "Command parsing failed.")}

    try:
        # --- Test Command ---
        if command_type == "test_command":
            return {
                "status": "success",
                "result": {
                    "message": "Test command executed successfully from GHCodeMCP_new",
                    "received_command": command_data
                }
            }

        # --- Get Context (Full Document Graph) ---
        elif command_type == "get_context":
            simplified = command_data.get("simplified", False) # Get simplified flag
            context_result = get_grasshopper_context(simplified=simplified) # Pass simplified flag
            # Returns dict with status/result
            return context_result

        # --- Expire Component and Get Info ---
        elif command_type == "expire_component":
            instance_guid = command_data.get("instance_guid")
            if not instance_guid:
                return {"status": "error", "result": "Missing 'instance_guid' for expire_component."}

            doc = ghenv.Component.OnPingDocument()
            if not doc:
                return {"status": "error", "result": "No active Grasshopper document."}

            # Return result directly as it's already properly formatted
            return expire_grasshopper_component(doc, instance_guid)

        # --- Get Specific Object(s) with Context ---
        elif command_type == "get_object" or command_type == "get_objects":
            instance_guids = []
            if command_type == "get_object":
                guid = command_data.get("instance_guid")
                if guid: instance_guids = [guid]
            else: # get_objects
                 guids = command_data.get("instance_guids", [])
                 if isinstance(guids, list): instance_guids = guids

            if not instance_guids:
                return {"status": "error", "result": "No instance GUID(s) provided."}

            context_depth = command_data.get("context_depth", 0)
            simplified = command_data.get("simplified", False) # Get simplified flag
            try: # Validate depth
                context_depth = int(context_depth)
                context_depth = max(0, min(context_depth, 3))
            except:
                context_depth = 0

            objects_result = get_objects_with_context(instance_guids, context_depth=context_depth, simplified=simplified) # Pass simplified flag
            # get_objects_with_context returns the dictionary directly or {}
            if objects_result or isinstance(objects_result, dict): # Check if it returned a dictionary (even empty)
                return {"status": "success", "result": objects_result}
            else:
                # Check if an error was logged during retrieval
                proc_error = sc.sticky.get("processing_error", "")
                if "get_objects" in proc_error or "finding object" in proc_error or "get param info" in proc_error or "get component info" in proc_error:
                     return {"status": "error", "result": "Error retrieving object info. Check component log."}
                else:
                     # Might be empty because GUIDs were invalid or referred to params within components
                     return {"status": "error", "result": "Target object(s) not found or not top-level components/params."}

        # --- Get Selected Object(s) with Context ---
        elif command_type == "get_selected":
            context_depth = command_data.get("context_depth", 0)
            simplified = command_data.get("simplified", False) # Get simplified flag
            try: # Validate depth
                context_depth = int(context_depth)
                context_depth = max(0, min(context_depth, 3))
            except:
                context_depth = 0

            selected_result = get_selected_objects(context_depth=context_depth, simplified=simplified) # Pass simplified flag
            # Returns dict with status/result
            return selected_result

        # --- Update Script Component (Code, Params, Desc) ---
        elif command_type == "update_script":
            instance_guid = command_data.get("instance_guid")
            if not instance_guid:
                return {"status": "error", "result": "Missing 'instance_guid' for update_script."}

            code = command_data.get("code")
            description = command_data.get("description")
            message_to_user = command_data.get("message_to_user")
            param_definitions = command_data.get("param_definitions")

            # Call the UI-thread-safe wrapper
            update_result = update_script_component(
                instance_guid,
                code=code,
                description=description,
                message_to_user=message_to_user,
                param_definitions=param_definitions
            )
            # Returns dict with status/result/warning
            return update_result

        # --- Update Script Component (Code Reference) ---
        elif command_type == "update_script_with_code_reference":
            instance_guid = command_data.get("instance_guid")
            if not instance_guid:
                return {"status": "error", "result": "Missing 'instance_guid' for code reference update."}

            file_path = command_data.get("file_path")
            param_definitions = command_data.get("param_definitions")
            description = command_data.get("description")
            name = command_data.get("name") # NickName
            force_code_reference = command_data.get("force_code_reference", False)

            # Call the UI-thread-safe wrapper
            update_ref_result = update_script_with_code_reference(
                instance_guid,
                file_path=file_path,
                param_definitions=param_definitions,
                description=description,
                name=name,
                force_code_reference=force_code_reference
            )
            # Returns dict with status/result/warning
            return update_ref_result

        # --- Execute Arbitrary Code ---
        elif command_type == "execute_code":
            code = command_data.get("code")
            if not code or not isinstance(code, str):
                return {"status": "error", "result": "Missing or invalid 'code' parameter."}
            # Execute synchronously
            exec_result = execute_code(code)
            return exec_result

        # --- Stop Server Command ---
        elif command_type == "stop":
            # Handled directly in the server loop. Signal loop to stop.
            sc.sticky["run_server"] = False
            return {"status": "success", "result": "Stop signal received. Server shutting down."}

        # --- Unknown Command ---
        else:
            unknown_msg = "Unknown command type received: {}".format(command_type)
            sc.sticky["processing_error"] = unknown_msg
            return {"status": "error", "result": unknown_msg}

    except Exception as e:
        # General exception during command processing logic
        tb_str = traceback.format_exc()
        error_msg = "Core error processing command '{}': {}\n{}".format(command_type, e, tb_str)
        sc.sticky["processing_error"] = error_msg # Log detailed error
        return {"status": "error", "result": "Server error processing command '{}'. Check component log.".format(command_type)}


# --- Socket Server Thread (Adapted from GHCodeMCP.py for robust HTTP handling) ---

def socket_server_thread():
    """Background thread function to run the socket server."""
    server_socket = None
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        sc.sticky["server_status"] = "Server listening on {}:{}".format(HOST, PORT)
        sc.sticky.pop("server_thread_error", None) # Clear previous thread error

        while sc.sticky.get("run_server", False): # Check the control flag
            conn = None
            addr = None
            try:
                server_socket.settimeout(1.0) # Timeout accept() to check run_server flag
                conn, addr = server_socket.accept()
                conn.settimeout(15.0) # Timeout for operations on this connection
                sc.sticky["last_connection_addr"] = str(addr)

                # --- Read Request (Robustly from GHCodeMCP.py) ---
                headers_raw = b""
                max_header_size = 8192
                while b"\r\n\r\n" not in headers_raw:
                    try:
                        chunk = conn.recv(1024)
                        if not chunk: break # Connection closed
                        headers_raw += chunk
                        if len(headers_raw) > max_header_size:
                            raise ValueError("Request headers too large (>{} bytes)".format(max_header_size))
                    except socket.timeout:
                         raise socket.timeout("Timeout reading request headers")
                    except Exception as read_err:
                         raise IOError("Error reading request headers: {}".format(read_err))

                if not headers_raw or b"\r\n\r\n" not in headers_raw:
                    if conn: conn.close(); conn = None
                    continue # Go back to accept

                try:
                     header_part_str, body_start_bytes = headers_raw.split(b"\r\n\r\n", 1)
                     header_part = header_part_str.decode('utf-8', errors='ignore')
                except Exception as decode_err:
                     raise ValueError("Error decoding request headers: {}".format(decode_err))

                header_lines = header_part.split("\r\n")
                if not header_lines: raise ValueError("Malformed headers (empty lines).")

                request_line = header_lines[0]
                request_parts = request_line.split(' ')
                if len(request_parts) < 2: raise ValueError("Malformed request line: {}".format(request_line))
                method = request_parts[0].upper()

                headers = {}
                for line in header_lines[1:]:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        headers[key.strip().lower()] = value.strip()

                # --- Handle OPTIONS (CORS Preflight) ---
                if method == "OPTIONS":
                    response_bytes = b"HTTP/1.1 200 OK\r\n" + \
                                     b"Access-Control-Allow-Origin: *\r\n" + \
                                     b"Access-Control-Allow-Methods: POST, OPTIONS, GET\r\n" + \
                                     b"Access-Control-Allow-Headers: Content-Type\r\n" + \
                                     b"Access-Control-Max-Age: 86400\r\n" + \
                                     b"Content-Length: 0\r\n" + \
                                     b"Connection: close\r\n\r\n"
                    conn.sendall(response_bytes)
                    conn.close(); conn = None
                    # Update status briefly?
                    # sc.sticky["server_status"] = "Handled OPTIONS from {}".format(addr)
                    continue # Go back to accept

                # --- Read Request Body ---
                body_bytes = body_start_bytes
                content_length = int(headers.get('content-length', 0))

                if content_length > 0:
                    max_body_size = 10 * 1024 * 1024 # 10MB limit
                    if content_length > max_body_size:
                         raise ValueError("Content-Length ({}) exceeds max size ({})".format(content_length, max_body_size))
                    while len(body_bytes) < content_length:
                        bytes_to_read = min(4096, content_length - len(body_bytes))
                        try:
                            chunk = conn.recv(bytes_to_read)
                            if not chunk: raise IOError("Connection closed unexpectedly reading body")
                            body_bytes += chunk
                        except socket.timeout: raise socket.timeout("Timeout reading request body")
                        except Exception as body_err: raise IOError("Error reading request body: {}".format(body_err))

                try:
                    body_str = body_bytes.decode('utf-8', errors='ignore').strip()
                except Exception as decode_body_err:
                     raise ValueError("Error decoding request body: {}".format(decode_body_err))

                # --- Process Command ---
                command_data = parse_command(body_str)
                result_dict = process_command(command_data) # Handles its own internal errors via sticky

                # --- Send Response ---
                status_code = 200
                status_text = "OK"
                if result_dict.get("status") == "error":
                    error_result_str = result_dict.get("result", "").lower()
                    # Use 400 for client errors (bad command/params)
                    if "parsing failed" in error_result_str or \
                       "invalid command format" in error_result_str or \
                       "missing 'instance_guid'" in error_result_str or \
                       "invalid 'code' parameter" in error_result_str or \
                       "no instance guid" in error_result_str or \
                       "object(s) not found" in error_result_str:
                        status_code = 400
                        status_text = "Bad Request"
                    elif "update failed (ui thread)" in error_result_str or \
                         "ui thread action failed" in error_result_str:
                         status_code = 500 # Error during critical UI operation
                         status_text = "Internal Server Error"
                    else: # Other server-side processing errors
                        status_code = 500
                        status_text = "Internal Server Error"

                response_body_json = json.dumps(result_dict, cls=GHEncoder, ensure_ascii=False) # Allow unicode
                response_body_bytes = response_body_json.encode('utf-8')

                status_line = "HTTP/1.1 {} {}".format(status_code, status_text)
                response_headers = [
                    status_line,
                    "Content-Type: application/json; charset=utf-8",
                    "Content-Length: {}".format(len(response_body_bytes)),
                    "Access-Control-Allow-Origin: *", # CORS header
                    "Connection: close" # Close connection after response
                ]
                http_response = "\r\n".join(response_headers) + "\r\n\r\n"
                response_bytes = http_response.encode('utf-8') + response_body_bytes

                conn.sendall(response_bytes)

                # Check for stop command type AFTER sending response
                if command_data.get("type") == "stop":
                    sc.sticky["server_status"] = "Received stop command. Shutting down."
                    sc.sticky["run_server"] = False # Signal loop to exit

            except socket.timeout as time_e:
                 error_msg = "Socket Timeout: {} ({})".format(time_e, addr if addr else 'unknown')
                 sc.sticky["server_thread_error"] = error_msg
                 if conn:
                     try: conn.sendall(b"HTTP/1.1 408 Request Timeout\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                     except: pass
            except (IOError, ValueError, Exception) as e: # Catch other errors during handling
                 tb_str = traceback.format_exc()
                 error_msg = "Error handling connection from {}: {}\n{}".format(addr if addr else 'unknown', e, tb_str)
                 sc.sticky["server_thread_error"] = error_msg
                 if conn:
                     try:
                          err_resp_body = json.dumps({"status": "error", "result": "Internal server error processing request."})
                          err_resp_bytes = err_resp_body.encode('utf-8')
                          err_http = "HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\nContent-Length: {}\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n".format(len(err_resp_bytes))
                          conn.sendall(err_http.encode('utf-8') + err_resp_bytes)
                     except Exception as send_err:
                          sc.sticky["server_thread_error"] += "\nAdditionally failed to send error response: {}".format(send_err)
            finally:
                if conn:
                    try: conn.shutdown(socket.SHUT_RDWR)
                    except: pass
                    conn.close()

        # End of while loop
        sc.sticky["server_status"] = "Server stopped."

    except Exception as e_serv: # Error binding or setting up socket
        tb_str = traceback.format_exc()
        error_msg = "FATAL: Socket server thread failed: {}\n{}".format(e_serv, tb_str)
        sc.sticky["server_thread_error"] = error_msg
        sc.sticky["server_status"] = "Server stopped (Setup Error)"
    finally:
        if server_socket:
            server_socket.close()
        # Ensure status reflects stop
        current_status = sc.sticky.get("server_status", "")
        if "listening" in current_status.lower():
            sc.sticky["server_status"] = "Server stopped."
        # Clean up flags/thread object
        sc.sticky["server_thread_obj"] = None
        # Ensure run_server flag is False if thread exits unexpectedly
        sc.sticky["run_server"] = False


# === Main Script Execution Logic (Runs whenever component updates - Adapted from GHCodeMCP.py) ===

# --- Component Inputs/Outputs ---
# >> REQUIRED Inputs:
#    1. RunServer (Boolean): Toggle to start/stop the server.
# << Optional Outputs:
#    1. status (Text): Outputs the server status string.
#    2. debug_output (Text): Outputs the contents of sc.sticky for debugging.

# Read input toggle (assume input is named "RunServer")
# Use locals().get() for safety if input doesn't exist initially
run_server_toggle = locals().get("RunServer", False)

# State management
server_was_intended_to_run = sc.sticky.get("server_is_intended_to_run", False)
server_thread_obj = sc.sticky.get("server_thread_obj")
# Check if thread object exists and is alive (more reliable check)
server_thread_is_alive = server_thread_obj and isinstance(server_thread_obj, threading.Thread) and server_thread_obj.isAlive()

# --- Start/Stop Server Logic ---
if run_server_toggle and not server_was_intended_to_run:
    # --- START SERVER ---
    if server_thread_is_alive:
         # A thread seems running, but intention was off. Log warning, update intention.
         ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Server thread may already be active. Check status.")
         sc.sticky["server_is_intended_to_run"] = True # Align intention
    else:
        # Intention is now ON, no thread alive, so START.
        ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "RunServer toggled ON. Starting server...")
        try:
            # Clear previous errors/status before starting
            sc.sticky.pop("server_thread_error", None)
            sc.sticky.pop("processing_error", None)
            sc.sticky.pop("last_update_error", None)
            sc.sticky.pop("connection_log", None)
            sc.sticky["server_status"] = "Starting..."

            sc.sticky["run_server"] = True # Set flag for the thread loop
            thread = threading.Thread(target=socket_server_thread)
            thread.daemon = True # Allow Rhino exit even if thread hangs
            thread.start()

            sc.sticky["server_thread_obj"] = thread
            sc.sticky["server_is_intended_to_run"] = True # Mark desired state

            time.sleep(0.1) # Brief pause for thread init

        except Exception as start_err:
             start_msg = "ERROR starting server thread: {}".format(start_err)
             ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, start_msg)
             sc.sticky["server_status"] = "Failed to start"
             sc.sticky["server_is_intended_to_run"] = False
             sc.sticky["server_thread_obj"] = None
             sc.sticky["run_server"] = False # Ensure flag is off

elif not run_server_toggle and server_was_intended_to_run:
    # --- STOP SERVER ---
    ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "RunServer toggled OFF. Signaling server to stop...")
    sc.sticky["run_server"] = False # Signal thread's loop to exit
    sc.sticky["server_is_intended_to_run"] = False # Mark desired state as OFF
    # Thread should stop itself. Don't join().
    # Clear the thread object reference immediately. Status updated by thread on exit.
    sc.sticky["server_thread_obj"] = None


# --- Status Reporting and Error Display (Runs every update) ---

# Check for errors logged by background thread or processing steps
# Use pop() to retrieve and clear the error message once displayed
# Order matters: show fatal thread errors first
server_error = sc.sticky.pop("server_thread_error", None)
if server_error:
    ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Server Thread Error:\n" + str(server_error)[:500]) # Show first 500 chars

proc_error = sc.sticky.pop("processing_error", None)
if proc_error:
    ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Processing/Parsing Error:\n" + str(proc_error)[:500])

update_error = sc.sticky.pop("last_update_error", None) # Pop update error after it's potentially added to result
if update_error:
     # Display as a persistent warning if it exists
     ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Last Update Error:\n" + str(update_error)[:500])

conn_log = sc.sticky.get("connection_log") # Keep log for debug output, don't pop

# Get current server status message from sticky
server_status_message = sc.sticky.get("server_status", "Server Status Unknown")

# Set component message bubble for primary feedback
ghenv.Component.Message = server_status_message

# Update component NickName based on status
current_nickname = COMPONENT_NICKNAME
# Check for errors first
has_error = server_error or proc_error or update_error or "error" in server_status_message.lower()

if has_error:
     current_nickname += " (Error)"
elif "listening" in server_status_message.lower():
    current_nickname += " (Running)"
elif "starting" in server_status_message.lower():
     current_nickname += " (Starting)"
elif "stopped" in server_status_message.lower() or "off" in server_status_message.lower():
     current_nickname += " (Stopped)"
else:
     current_nickname += " (Idle)" # Default if status is unclear
ghenv.Component.NickName = current_nickname


# --- Optional Outputs ---
# These lines will assign values to variables named 'status' and 'debug_output'.
# If output parameters with these names exist on the GH component, Grasshopper
# will automatically connect them.

# Output the status string
status = server_status_message

# Output debug information
debug_info_list = ["--- sc.sticky contents ({}) ---".format(time.strftime("%H:%M:%S"))]
if hasattr(sc, "sticky"):
    try:
        sticky_items = sorted(sc.sticky.items()) # Sort by key for consistency
        if not sticky_items:
            debug_info_list.append("(sticky is empty)")
        else:
            for key, value in sticky_items:
                 value_str = ""
                 try:
                     if key == "server_thread_obj" and isinstance(value, threading.Thread):
                         thread_state = "Alive" if value.isAlive() else "Not Alive"
                         value_str = "<Thread ID: {}, State: {}>".format(value.ident, thread_state)
                     elif key == "connection_log" and isinstance(value, str) and len(value) > 250:
                          value_str = repr(value[:250]) + "...(log truncated)"
                     else:
                         # General repr, truncate if too long
                         repr_val = repr(value)
                         if len(repr_val) > 250:
                              value_str = repr_val[:250] + "...(truncated)"
                         else:
                              value_str = repr_val
                 except Exception as repr_err:
                     value_str = "[Error getting repr: {}]".format(repr_err)

                 debug_info_list.append(u"{}: {}".format(key, value_str)) # Use unicode literals
    except Exception as debug_err:
        debug_info_list.append("! Error reading sticky: {}".format(debug_err))
else:
    debug_info_list.append("(Attribute 'sticky' not found on 'sc')")

debug_output = "\n".join(debug_info_list)
