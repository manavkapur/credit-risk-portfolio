"""LiteLLM transport, optional Langfuse telemetry and deterministic NeMo rails."""
import os
import json
from contextlib import nullcontext
from functools import lru_cache
from guardrails import Guard, Validator, register_validator
from guardrails.settings import settings
settings.rc.enable_metrics = False
from guardrails.validator_base import PassResult, FailResult
from nemoguardrails import LLMRails, RailsConfig
from src.qa_controls import admission, GuardrailError


@register_validator(name='portfolio_input_policy',data_type='string')
class PortfolioPolicy(Validator):
    def _validate(self,value,metadata):
        try:
            admission(value)
            if not 1<=len(value.strip())<=2000:
                return FailResult(error_message='Question length invalid')
            return PassResult()
        except GuardrailError as exc:
            return FailResult(error_message=str(exc))


@lru_cache(maxsize=1)
def input_guard():
    guard=Guard().use(PortfolioPolicy(on_fail='exception'))
    guard.configure(allow_metrics_collection=False)
    return guard


def check_question(question):
    # Fresh engine avoids sharing mutable Colang state between sessions.
    config=RailsConfig.from_content(yaml_content='models: []\nrails:\n  input:\n    flows:\n      - portfolio input\n',
        colang_content='''define flow portfolio input
  $allowed = execute portfolio_policy
  if not $allowed
    bot refuse to respond
    stop
''')
    rails=LLMRails(config)
    async def policy(context=None):
        try:
            input_guard().validate(context.get('user_message',''))
            return True
        except Exception:
            return False
    rails.register_action(policy,name='portfolio_policy')
    response=rails.generate(messages=[{'role':'user','content':question}],
        options={'rails':['input'],'output_vars':['allowed']})
    if not response.output_data or response.output_data.get('allowed') is not True:
        raise GuardrailError('The portfolio input policy rejected this request. Ask a factual portfolio aggregation.')


def generate_plan(prompt,question,api_key,model,schema):
    import litellm
    # Never send credentials or portfolio records to telemetry.
    observation=nullcontext(None)
    client=None
    if os.getenv('LANGFUSE_PUBLIC_KEY') and os.getenv('LANGFUSE_SECRET_KEY'):
        from langfuse import get_client
        client=get_client()
        observation=client.start_as_current_observation(name='portfolio-plan',as_type='generation',
            model=model,metadata={'question_length':len(question),'policy':'portfolio-v3'})
    with observation as span:
        if span:
            span.update(metadata={'session_note':'portfolio application'})
        response=litellm.completion(model=model if '/' in model else 'openai/'+model,
            api_key=api_key,messages=[{'role':'system','content':prompt},{'role':'user','content':question}],
            response_format={'type':'json_schema','json_schema':{'name':'QueryPlan','strict':True,'schema':schema.model_json_schema()}},
            max_tokens=600,timeout=25,num_retries=0)
        plan=schema.model_validate_json(response.choices[0].message.content)
        # Guardrails AI independently validates the structured output without reasks.
        guard=Guard.for_pydantic(output_class=schema)
        guard.configure(allow_metrics_collection=False)
        outcome=guard.validate(plan.model_dump_json(),num_reasks=0)
        if not outcome.validation_passed:
            raise GuardrailError('Structured output failed Guardrails AI validation')
        if span:
            usage=response.usage
            span.update(usage_details={'input':usage.prompt_tokens,'output':usage.completion_tokens},
                        metadata={'supported':plan.supported,'metric':plan.metric})
    if client:
        client.flush()
    return plan
