from openai import OpenAI
import json


OPENAI_API_KEY = ''

client = OpenAI(api_key=OPENAI_API_KEY)


def invoke_openai(prompt,model_id="gpt-4o-mini",object=True):
    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content
    cost = parse_openai_response(response,model_id)
    output_json = parse_output(text,object=object)
    return output_json,cost


def parse_openai_response(response,model_id):
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    INPUT_PRICE = OPENAI_PRICING[model_id]['input']
    OUTPUT_PRICE = OPENAI_PRICING[model_id]['output']
    cost = (input_tokens * INPUT_PRICE) + (output_tokens * OUTPUT_PRICE)
    return cost

def parse_output(output,object=False):
    try:
        if object:
            start = output.index("{")
            end = output.rfind("}") + 1
        else:
            # Strip everything except the JSON block
            start = output.index("[")
            end = output.rfind("]") + 1
        json_str = output[start:end]
        # Optional: print cleaned JSON string
        print("Extracted JSON:\n", json_str)
        # Parse the JSON
        parsed = json.loads(json_str)
        return parsed

    except (ValueError, json.JSONDecodeError) as e:
        print("Failed to parse JSON:", e)
        return None


print(invoke_openai("Give me a list of three colors in JSON array format.",model_id="gpt-4o-mini",object=False))


OPENAI_PRICING = {
    # ───────────────
    # GPT-4.1 family
    # ───────────────
    'gpt-4.1-mini': {
        'input': 0.40 / 1_000_000,    # $0.40 / 1M
        'output': 1.60 / 1_000_000    # $1.60 / 1M
    },
    'gpt-4.1': {
        'input': 2.00 / 1_000_000,    # $2.00 / 1M
        'output': 8.00 / 1_000_000    # $8.00 / 1M
    },

    # ───────────────
    # GPT-4o family
    # ───────────────
    'gpt-4o-mini': {
        'input': 0.15 / 1_000_000,    # $0.15 / 1M
        'output': 0.60 / 1_000_000    # $0.60 / 1M
    },
    'gpt-4o': {
        'input': 5.00 / 1_000_000,    # $5.00 / 1M
        'output': 15.00 / 1_000_000   # $15.00 / 1M
    },

    # ───────────────
    # GPT-5 family
    # ───────────────
    'gpt-5-nano': {
        'input': 0.05 / 1_000_000,   # $0.05 / 1M
        'output': 0.40 / 1_000_000   # $0.40 / 1M
    },
    'gpt-5-mini': {
        'input': 0.25 / 1_000_000,    # $0.25 / 1M
        'output': 2.00 / 1_000_000    # $2.00 / 1M
    },
    'gpt-5': {
        'input': 1.25 / 1_000_000,    # $1.25 / 1M
        'output': 10.00 / 1_000_000   # $10.00 / 1M
    }
}
