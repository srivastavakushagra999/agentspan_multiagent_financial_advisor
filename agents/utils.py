import re

def strip_json_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1) if match else text

def parse_structured_output(raw_result, model_class):
    if isinstance(raw_result, str):
        json_str = strip_json_fences(raw_result)
        return model_class.model_validate_json(json_str)
    return model_class.model_validate(raw_result)
