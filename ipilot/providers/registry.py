from dataclasses import dataclass


@dataclass
class ProviderSpec:
    name: str
    default_model: str
    default_api_base: str = ""

PROVIDERS = {
    "stepfun": ProviderSpec(
        name="stepfun",
        default_model="step-3.5-flash-2603",
        default_api_base="https://api.stepfun.com/v1",
    )
}