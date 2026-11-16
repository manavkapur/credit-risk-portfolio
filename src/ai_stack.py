"""LiteLLM routing, opt-in Langfuse metadata tracing and framework guardrails."""
import os
from functools import lru_cache
from contextlib import nullcontext
from src.qa_controls import admission, GuardrailError


@lru_cache(maxsize=1)
def nemo():
    from nemoguardrails import RailsConfig, LLMRails
    config=RailsConfig.from_content(yaml_content='''
models: []
rails:
  input:
    flows:
      - portfolio input check
''',colang_content='''
define flow portfolio input check
  $allowed = execute portfolio_allowed
  if not $allowed
    bot refuse to respond
    stop
''')
    rails=LLMRails(config)
    async def allowed(context):
        try:
            admission(context.get('user_message',''))
            return True
        except GuardrailError:
            return False
    rails.register_action(allowed,name='portfolio_allowed')
    return rails


def check_input(question):
    result=nemo().generate(messages=[{'role':'user','content':question}],options={'rails':['input']})
    if result.response[0]['content'] != question:
        raise GuardrailError('NeMo input rail declined this request. Ask a factual portfolio aggregation.')


def validate_output(raw,schema):
    from guardrails import Guard
    # No automatic repair/reasks: unvalidated plans never reach SQL execution.
    outcome=Guard.for_pydantic(output_class=schema).parse(raw,num_reasks=0)
    if not outcome.validation_passed:
        raise GuardrailError('Guardrails AI rejected the query plan.')
    return schema.model_validate(outcome.validated_output)


def completion_plan(prompt,question,key,model,schema):
    import litellm
    observation=nullcontext(None)
    # Opt-in metadata only: do not send question text, rows, secrets or SQL results.
    if os.getenv('LANGFUSE_PUBLIC_KEY') and os.getenv('LANGFUSE_SECRET_KEY'):
        from langfuse import get_client
        observation=get_client().start_as_current_observation(name='portfolio-plan',as_type='generation',model=model,
            metadata={'question_characters':len(question),'prompt_version':'qa-v3'})
    with observation as trace:
        response=litellm.completion(model=model,api_key=key,
            messages=[{'role':'system','content':prompt},{'role':'user','content':question}],
            response_format=schema,max_tokens=600,timeout=25,num_retries=0)
        if trace:
            trace.update(usage_details={'input':response.usage.prompt_tokens,'output':response.usage.completion_tokens})
        return validate_output(response.choices[0].message.content,schema)
