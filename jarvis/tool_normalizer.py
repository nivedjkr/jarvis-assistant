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


def _validate_tool_call(
    name: Any,
    args: Any,
    valid_names: Optional[Set[str]]
) -> Optional[Dict[str, Any]]:
    """
    Validates name and args according to strict criteria:
    1. Name must be a non-empty string.
    2. If valid_names is provided, name MUST be in valid_names.
    3. Args must be a dict (or parsed from JSON string into dict).
    Returns normalized dict or None if invalid.
    """
    if not name or not isinstance(name, str):
        return None

    tool_name = name.strip()
    if not tool_name:
        return None

    if valid_names is not None and tool_name not in valid_names:
        return None

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
        "name": tool_name,
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

    return normalized if normalized else None
