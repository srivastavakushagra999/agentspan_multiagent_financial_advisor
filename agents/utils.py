import re
def parse_structured_output(raw_result, model_class):
    if isinstance(raw_result, str):
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_result, re.DOTALL)
        json_str = match.group(1) if match else raw_result
        return model_class.model_validate_json(json_str)
    return model_class.model_validate(raw_result)
