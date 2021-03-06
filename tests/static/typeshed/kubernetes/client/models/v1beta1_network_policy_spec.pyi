# Stubs for kubernetes.client.models.v1beta1_network_policy_spec (Python 2)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

class V1beta1NetworkPolicySpec:
    swagger_types: Any = ...
    attribute_map: Any = ...
    discriminator: Any = ...
    egress: Any = ...
    ingress: Any = ...
    pod_selector: Any = ...
    policy_types: Any = ...
    def __init__(self, egress: Optional[Any] = ..., ingress: Optional[Any] = ..., pod_selector: Optional[Any] = ..., policy_types: Optional[Any] = ...) -> None: ...
    @property
    def egress(self): ...
    @egress.setter
    def egress(self, egress: Any) -> None: ...
    @property
    def ingress(self): ...
    @ingress.setter
    def ingress(self, ingress: Any) -> None: ...
    @property
    def pod_selector(self): ...
    @pod_selector.setter
    def pod_selector(self, pod_selector: Any) -> None: ...
    @property
    def policy_types(self): ...
    @policy_types.setter
    def policy_types(self, policy_types: Any) -> None: ...
    def to_dict(self): ...
    def to_str(self): ...
    def __eq__(self, other: Any): ...
    def __ne__(self, other: Any): ...
