"""
Tool Call Normalization Layer for JARVIS.

Normalizes diverse LLM tool-call representations (native OpenAI tool_calls,
text JSON objects, arrays of JSON tool calls, markdown-wrapped JSON) into a single
standardized internal dictionary format:

[
    {
        "id": "call_...",
        "name": "tool_name",
        "arguments": {"arg1": "val1"}
    }
]
"""

import json
import re
import uuid
from typing import Dict, List, Optional, Any, Set, Union


def _extract_registered_names(registered_tools: Optional[Any]) -> Optional[Set[str]]:
    """
    Extract a set of valid tool name strings from registered_tools, which can be:
    - Set or List of strings: ['search_obsidian', 'check_email']
    - Dict of tools: {'search_obsidian': <fn>, 'check_email': <fn>}
    - List of OpenAI schema dicts: [{'type': 'function', 'function': {'name': 'search_obsidian'}}]
    """
    if registered_tools is None:
        return None

    if isinstance(registered_tools, set):
        return {str(x) for x in registered_tools}

    if isinstance(registered_tools, dict):
        return {str(k) for k in registered_tools.keys()}

    if isinstance(registered_tools, (list, tuple)):
        names = set()
        for item in registered_tools:
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, dict):
                if item.get("type") == "function" and isinstance(item.get("function"), dict):
                    fn_name = item["function"].get("name")
                    if fn_name:
                        names.add(str(fn_name))
                elif "name" in item:
                    names.add(str(item["name"]))
        return names

    return None


DEFAULT_TOOL_ALIASES: Dict[str, str] = {
    "git_stage": "git_add",
    "stage_files": "git_add",
    "git_commit_and_push": "git_add_commit_push",
    "git_push_all": "git_add_commit_push",
    "push_to_github": "git_add_commit_push",
    "check_calendar": "list_calendar_events",
    "check_calendar_events": "list_calendar_events",
    "get_calendar": "list_calendar_events",
    "get_calendar_events": "list_calendar_events",
    "show_calendar": "list_calendar_events",
    "view_calendar": "list_calendar_events",
    "add_calendar_event": "create_calendar_event",
    "add_event": "create_calendar_event",
    "schedule_event": "create_calendar_event",
    "create_event": "create_calendar_event",
    "search_calendar": "search_calendar_events",
    "find_calendar_events": "search_calendar_events",
    "find_events": "search_calendar_events",
    "remove_calendar_event": "delete_calendar_event",
    "cancel_event": "delete_calendar_event",
    "delete_event": "delete_calendar_event",
    "search_notes": "search_obsidian",
    "obsidian_search": "search_obsidian",
    "find_obsidian_notes": "search_obsidian",
    "create_note": "create_obsidian_note",
    "add_note": "create_obsidian_note",
    "link_notes": "link_obsidian_notes",
    "connect_notes": "link_obsidian_notes",
    "append_note": "append_obsidian_note",
    "append_to_note": "append_obsidian_note",
    "append_obsidian_note": "append_obsidian_note",
    "web_search": "web_search_live",
    "google_search": "web_search_live",
    "run_terminal": "run_command",
    "terminal": "run_command",
    "bash": "run_command",
    "shell": "run_command",
    "cmd": "run_command",
    "inspect_dir": "inspect_project",
    "inspect_folder": "inspect_project",
    "run_test": "run_tests",
}


def resolve_tool_alias(name: str, valid_names: Optional[Set[str]] = None) -> Optional[str]:
    """
    Resolves tool name against aliases and valid_names.
    """
    if not name or not isinstance(name, str):
        return None
    cleaned = name.strip()
    if not cleaned:
        return None

    if valid_names is None:
        return DEFAULT_TOOL_ALIASES.get(cleaned.lower(), cleaned)

    if cleaned in valid_names:
        return cleaned

    cleaned_lower = cleaned.lower()
    if cleaned_lower in DEFAULT_TOOL_ALIASES:
        target = DEFAULT_TOOL_ALIASES[cleaned_lower]
        if target in valid_names:
            return target

    return None


def _validate_tool_call(
    name: Any,
    args: Any,
    valid_names: Optional[Set[str]]
) -> Optional[Dict[str, Any]]:
    """
    Validates name and args according to strict criteria:
    1. Name must be a non-empty string.
    2. If valid_names is provided, name MUST be in valid_names (or resolve via alias).
    3. Args must be a dict (or parsed from JSON string into dict).
    Returns normalized dict or None if invalid.
    """
    if not name or not isinstance(name, str):
        return None

    tool_name = name.strip()
    if not tool_name:
        return None

    resolved_name = resolve_tool_alias(tool_name, valid_names)
    if valid_names is not None and not resolved_name:
        return None

    final_name = resolved_name if resolved_name else tool_name

    if isinstance(args, str):
        try:
            parsed_args = json.loads(args)
            if isinstance(parsed_args, dict):
                args = parsed_args
            else:
                return None
        except Exception:
            return None

    if args is None:
        args = {}

    if not isinstance(args, dict):
        return None

    return {
        "name": final_name,
        "arguments": args
    }


def _extract_tool_call_from_dict(
    item: Dict[str, Any],
    valid_names: Optional[Set[str]]
) -> Optional[Dict[str, Any]]:
    """
    Attempts to parse a dictionary item as a tool call.
    Supported key patterns:
    - {"tool": "name", "args": {...}}
    - {"name": "name", "arguments": {...}}
    - {"action": "name", "action_input": {...}}
    - {"function": "name", "parameters": {...}}
    """
    if not isinstance(item, dict):
        return None

    # Candidate name keys
    name = item.get("tool") or item.get("name") or item.get("action") or item.get("function")
    
    # If name is still None, check nested "function" object if present
    if not name and isinstance(item.get("function"), dict):
        name = item["function"].get("name")
        args_val = item["function"].get("arguments") or item["function"].get("args")
    else:
        # Candidate args keys
        if "args" in item:
            args_val = item.get("args")
        elif "arguments" in item:
            args_val = item.get("arguments")
        elif "action_input" in item:
            args_val = item.get("action_input")
        elif "parameters" in item:
            args_val = item.get("parameters")
        elif "params" in item:
            args_val = item.get("params")
        else:
            args_val = {}

    validated = _validate_tool_call(name, args_val, valid_names)
    if validated:
        call_id = item.get("id") or f"call_{uuid.uuid4().hex[:8]}"
        validated["id"] = call_id
        return validated

    return None


def _extract_xml_tool_calls(
    text: str,
    valid_names: Optional[Set[str]]
) -> List[Dict[str, Any]]:
    """
    Extracts XML or tag-based tool calls commonly emitted by models such as
    NVIDIA Nemotron, Command-R, and Mistral/Llama:
    e.g.
    <tool_call>
    <function=inspect_project>
    <parameter=path>
    D:\\phantomX
    </parameter>
    </function>
    </tool_call>
    or <tool_call>{"name": "...", "arguments": {...}}</tool_call>
    """
    results: List[Dict[str, Any]] = []
    if not text or not isinstance(text, str):
        return results

    # 1. Blocks enclosed in <tool_call>...</tool_call> or <function_call>...</function_call>
    call_blocks = re.findall(r"<(?:tool_call|function_call)>([\s\S]*?)</(?:tool_call|function_call)>", text, re.IGNORECASE)

    # 2. If no wrapper tags, but has <function[=:\s] in raw text
    if not call_blocks and re.search(r"<function[=:\s]", text, re.IGNORECASE):
        call_blocks = [text]

    for block in call_blocks:
        block_clean = block.strip()

        # Check if block contains JSON directly: <tool_call>{"name": ...}</tool_call> or array [...]
        if (block_clean.startswith("{") and block_clean.endswith("}")) or (block_clean.startswith("[") and block_clean.endswith("]")):
            try:
                data = json.loads(block_clean)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        tc_dict = _extract_tool_call_from_dict(item, valid_names)
                        if tc_dict:
                            results.append(tc_dict)
                if results:
                    continue
            except Exception:
                pass

        # Parse <function=name> ... </function> or <function:name> ... </function> or <function name="name"> ... </function>
        fn_pattern = r"<function(?:[=:]|\s+name=)[\"\\']?([a-zA-Z0-9_\-\.]+)[\"\\']?>([\s\S]*?)(?:</function(?::[a-zA-Z0-9_\-\.]+)?>|$)"
        matches = re.findall(fn_pattern, block, re.IGNORECASE)
        for fn_name, fn_body in matches:
            fn_name = fn_name.strip()
            resolved = resolve_tool_alias(fn_name, valid_names)
            if valid_names is not None and not resolved:
                continue
            effective_name = resolved if resolved else fn_name

            args = {}
            # Parse <parameter=name>val</parameter> or <parameter:name>val</parameter> or <parameter name="name">val</parameter>
            param_pattern = r"<parameter(?:[=:]|\s+name=)[\"\\']?([a-zA-Z0-9_\-\.]+)[\"\\']?>([\s\S]*?)(?:</parameter(?::[a-zA-Z0-9_\-\.]+)?>|$)"
            param_matches = re.findall(param_pattern, fn_body, re.IGNORECASE)
            for p_name, p_val in param_matches:
                p_name = p_name.strip()
                p_val = p_val.strip()
                try:
                    parsed_val = json.loads(p_val)
                    args[p_name] = parsed_val
                except Exception:
                    args[p_name] = p_val

            validated = _validate_tool_call(effective_name, args, valid_names)
            if validated:
                validated["id"] = f"call_{uuid.uuid4().hex[:8]}"
                results.append(validated)

    return results


def normalize_tool_calls(
    response: Any,
    registered_tools: Optional[Any] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    Normalizes native or text-based tool calls from an LLM response.

    Args:
        response: Raw response from LLM, ChatCompletion object, message object, dict, or string.
        registered_tools: Set, List, or Dict of valid registered tool names/schemas.

    Returns:
        List of normalized tool call dicts (with 'id', 'name', 'arguments'),
        or None if the response is genuine user-facing text.
    """
    valid_names = _extract_registered_names(registered_tools)
    normalized: List[Dict[str, Any]] = []

    # --- STEP 1: Check Native Structured tool_calls ---
    native_calls = None
    if hasattr(response, "tool_calls") and response.tool_calls:
        native_calls = response.tool_calls
    elif hasattr(response, "choices") and response.choices:
        choice_msg = getattr(response.choices[0], "message", None)
        if choice_msg and getattr(choice_msg, "tool_calls", None):
            native_calls = choice_msg.tool_calls
    elif isinstance(response, dict) and response.get("tool_calls"):
        native_calls = response.get("tool_calls")

    if native_calls:
        for tc in native_calls:
            call_id = getattr(tc, "id", None) or (tc.get("id") if isinstance(tc, dict) else None) or f"call_{uuid.uuid4().hex[:8]}"
            fn_obj = getattr(tc, "function", None) or (tc.get("function") if isinstance(tc, dict) else None)
            
            if fn_obj:
                name = getattr(fn_obj, "name", None) or (fn_obj.get("name") if isinstance(fn_obj, dict) else None)
                args = getattr(fn_obj, "arguments", None) or (fn_obj.get("arguments") if isinstance(fn_obj, dict) else None)
            elif isinstance(tc, dict):
                name = tc.get("name") or tc.get("tool")
                args = tc.get("arguments") or tc.get("args")
            else:
                name, args = None, None

            validated = _validate_tool_call(name, args, valid_names)
            if validated:
                validated["id"] = call_id
                normalized.append(validated)

        if normalized:
            return normalized

    # --- STEP 2: Inspect Assistant Text / Content ---
    text_content = ""
    if isinstance(response, str):
        text_content = response
    elif hasattr(response, "choices") and response.choices:
        msg = getattr(response.choices[0], "message", None)
        if msg:
            text_content = getattr(msg, "content", "") or ""
    elif hasattr(response, "content"):
        text_content = getattr(response, "content", "") or ""
    elif isinstance(response, dict):
        text_content = response.get("content") or response.get("text") or ""

    if not text_content or not isinstance(text_content, str):
        return None

    cleaned_text = text_content.strip()
    if not cleaned_text:
        return None

    # Extraction candidate strategies
    json_candidates: List[Any] = []

    # Strategy A: Code block extraction
    code_block_matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_text, re.IGNORECASE)
    for block in code_block_matches:
        try:
            parsed = json.loads(block.strip())
            json_candidates.append(parsed)
        except Exception:
            pass

    # Strategy B: Try full text JSON parse
    if not json_candidates:
        try:
            parsed = json.loads(cleaned_text)
            json_candidates.append(parsed)
        except Exception:
            pass

    # Strategy C: Regex find JSON objects or arrays inside text
    if not json_candidates:
        # Find JSON arrays [...]
        array_matches = re.findall(r"(\[\s*\{[\s\S]*?\}\s*\])", cleaned_text)
        for arr_str in array_matches:
            try:
                parsed = json.loads(arr_str)
                if isinstance(parsed, list):
                    json_candidates.append(parsed)
            except Exception:
                pass

        # Find JSON objects {...}
        obj_matches = re.findall(r"(\{\s*\"(?:tool|name|action|function)\"[\s\S]*?\})", cleaned_text)
        for obj_str in obj_matches:
            try:
                parsed = json.loads(obj_str)
                if isinstance(parsed, dict):
                    json_candidates.append(parsed)
            except Exception:
                pass

    # --- STEP 3: Normalize Candidates ---
    for candidate in json_candidates:
        if isinstance(candidate, list):
            for item in candidate:
                if isinstance(item, dict):
                    tc_dict = _extract_tool_call_from_dict(item, valid_names)
                    if tc_dict:
                        normalized.append(tc_dict)
        elif isinstance(candidate, dict):
            tc_dict = _extract_tool_call_from_dict(candidate, valid_names)
            if tc_dict:
                normalized.append(tc_dict)

    # Strategy D: XML / Tag-based Tool Call Extraction (Nemotron / Command-R / Mistral)
    xml_calls = _extract_xml_tool_calls(cleaned_text, valid_names)
    if xml_calls:
        # Avoid duplicating calls if already parsed via JSON
        existing_keys = {(c["name"], json.dumps(c.get("arguments", {}), sort_keys=True)) for c in normalized}
        for xc in xml_calls:
            k = (xc["name"], json.dumps(xc.get("arguments", {}), sort_keys=True))
            if k not in existing_keys:
                normalized.append(xc)
                existing_keys.add(k)

    return normalized if normalized else None


from enum import Enum


class ResponseClassification(str, Enum):
    TOOL_CALL = "TOOL_CALL"
    INTERMEDIATE = "INTERMEDIATE"
    FINAL = "FINAL"


def strip_raw_tool_tags(text: str) -> str:
    """
    Strips any leaked <tool_call>...</tool_call>, <function=...>...</function>,
    or <function_call> XML tags from user-facing text responses.
    """
    if not text or not isinstance(text, str):
        return ""
    # Strip complete tool call / function blocks
    cleaned = re.sub(r"<(?:tool_call|function_call)>[\s\S]*?</(?:tool_call|function_call)>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<function(?:[=:]|\s+name=)[\"\\']?[^>]+[\"\\']?>[\s\S]*?(?:</function(?::[^>]+)?>|$)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<parameter(?:[=:]|\s+name=)[\"\\']?[^>]+[\"\\']?>[\s\S]*?(?:</parameter(?::[^>]+)?>|$)", "", cleaned, flags=re.IGNORECASE)
    # Strip any dangling/unclosed tags
    cleaned = re.sub(r"</?(?:tool_call|function_call|function|parameter)[^>]*>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def classify_response(
    response: Any,
    registered_tools: Optional[Any] = None
) -> ResponseClassification:
    """
    Classifies LLM response into TOOL_CALL or FINAL.
    """
    normalized = normalize_tool_calls(response, registered_tools=registered_tools)
    if normalized:
        return ResponseClassification.TOOL_CALL

    # Check if the model emitted an explicit XML tool call tag (<tool_call>, <function=)
    text_content = ""
    if isinstance(response, str):
        text_content = response
    elif hasattr(response, "content"):
        text_content = getattr(response, "content", "") or ""
    elif hasattr(response, "choices") and response.choices:
        msg = getattr(response.choices[0], "message", None)
        if msg:
            text_content = getattr(msg, "content", "") or ""
    elif isinstance(response, dict):
        text_content = response.get("content") or response.get("text") or ""

    if text_content and re.search(r"<(?:tool_call|function_call|function[=:\s])", text_content, re.IGNORECASE):
        return ResponseClassification.TOOL_CALL

    return ResponseClassification.FINAL


def is_unresolved_tool_call(
    content: Any,
    registered_tools: Optional[Any] = None
) -> bool:
    """
    Final Response Firewall check. Returns True if content contains unexecuted tool call XML or JSON.
    Catches both registered tool calls and unexecuted/unregistered tool calls or leaked tags.
    """
    if not content:
        return False

    text_content = ""
    if isinstance(content, str):
        text_content = content
    elif hasattr(content, "content"):
        text_content = getattr(content, "content", "") or ""
    elif isinstance(content, dict):
        text_content = content.get("content") or content.get("text") or ""

    if not text_content or not isinstance(text_content, str):
        return False

    # 1. Any XML tool-call tags (<tool_call>, <function=, <function_call>, etc.)
    if re.search(r"</?(?:tool_call|function_call)\b|<function[=:\s]", text_content, re.IGNORECASE):
        return True

    # 2. Strict check with registered_tools if provided
    if registered_tools is not None:
        normalized = normalize_tool_calls(text_content, registered_tools=registered_tools)
        if normalized:
            return True

    # 3. Check if text is raw tool call JSON (even if tool name is unregistered)
    unregistered = normalize_tool_calls(text_content, registered_tools=None)
    if unregistered:
        return True

    return False

