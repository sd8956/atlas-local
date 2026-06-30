from __future__ import annotations

from typing import Any

from atlas_local.collectors.aws.base import AwsCollector


def pages(client: Any, operation: str, **kwargs: Any) -> list[Any]:
    paginator = client.get_paginator(operation)
    out: list[Any] = []
    for page in paginator.paginate(**kwargs):
        out.append(page)
    return out


class AccountIdentityCollector(AwsCollector):
    service = "sts"
    regional = False

    def collect(self, session: Any, region: str | None) -> dict[str, Any]:
        errors: list[str] = []
        identity = self.safe_call(lambda: session.client("sts").get_caller_identity(), errors, "get_caller_identity")
        return self.envelope(account_id=(identity or {}).get("Account"), region=None, items={"identity": identity}, errors=errors)


class Ec2InventoryCollector(AwsCollector):
    service = "ec2"

    def collect(self, session: Any, region: str | None) -> dict[str, Any]:
        errors: list[str] = []
        ec2 = session.client("ec2", region_name=region)
        items = {
            "instances": self.safe_call(lambda: pages(ec2, "describe_instances"), errors, "describe_instances"),
            "volumes": self.safe_call(lambda: pages(ec2, "describe_volumes"), errors, "describe_volumes"),
            "snapshots": self.safe_call(lambda: pages(ec2, "describe_snapshots", OwnerIds=["self"]), errors, "describe_snapshots"),
            "amis": self.safe_call(lambda: pages(ec2, "describe_images", Owners=["self"]), errors, "describe_images"),
            "vpcs": self.safe_call(lambda: pages(ec2, "describe_vpcs"), errors, "describe_vpcs"),
            "subnets": self.safe_call(lambda: pages(ec2, "describe_subnets"), errors, "describe_subnets"),
            "route_tables": self.safe_call(lambda: pages(ec2, "describe_route_tables"), errors, "describe_route_tables"),
            "nat_gateways": self.safe_call(lambda: pages(ec2, "describe_nat_gateways"), errors, "describe_nat_gateways"),
            "internet_gateways": self.safe_call(lambda: pages(ec2, "describe_internet_gateways"), errors, "describe_internet_gateways"),
            "security_groups": self.safe_call(lambda: pages(ec2, "describe_security_groups"), errors, "describe_security_groups"),
        }
        return self.envelope(account_id=None, region=region, items=items, errors=errors)


class GenericAwsCollector(AwsCollector):
    def __init__(self, service: str, calls: dict[str, tuple[str, dict[str, Any]]], regional: bool = True):
        self.service = service
        self.calls = calls
        self.regional = regional

    def collect(self, session: Any, region: str | None) -> dict[str, Any]:
        errors: list[str] = []
        client = session.client(self.service, region_name=region) if self.regional else session.client(self.service)
        items = {}
        for key, (operation, kwargs) in self.calls.items():
            def call(op=operation, kw=kwargs):
                try:
                    return pages(client, op, **kw)
                except Exception:
                    return getattr(client, op)(**kw)
            items[key] = self.safe_call(call, errors, operation)
        return self.envelope(account_id=None, region=region if self.regional else None, items=items, errors=errors)


COLLECTORS: list[AwsCollector] = [
    AccountIdentityCollector(),
    Ec2InventoryCollector(),
    GenericAwsCollector("rds", {"db_instances": ("describe_db_instances", {}), "db_clusters": ("describe_db_clusters", {})}),
    GenericAwsCollector("lambda", {"functions": ("list_functions", {})}),
    GenericAwsCollector("apigateway", {"rest_apis": ("get_rest_apis", {})}),
    GenericAwsCollector("ecs", {"clusters": ("list_clusters", {})}),
    GenericAwsCollector("ecr", {"repositories": ("describe_repositories", {})}),
    GenericAwsCollector("elbv2", {"load_balancers": ("describe_load_balancers", {}), "target_groups": ("describe_target_groups", {})}),
    GenericAwsCollector("iam", {"roles": ("list_roles", {}), "policies": ("list_policies", {"Scope": "Local"})}, regional=False),
    GenericAwsCollector("s3", {"buckets": ("list_buckets", {})}, regional=False),
    GenericAwsCollector("cloudwatch", {"alarms": ("describe_alarms", {})}),
    GenericAwsCollector("logs", {"log_groups": ("describe_log_groups", {})}),
    GenericAwsCollector("dynamodb", {"tables": ("list_tables", {})}),
    GenericAwsCollector("events", {"rules": ("list_rules", {})}),
    GenericAwsCollector("sqs", {"queues": ("list_queues", {})}),
    GenericAwsCollector("sns", {"topics": ("list_topics", {})}),
    GenericAwsCollector("cloudformation", {"stacks": ("describe_stacks", {})}),
    GenericAwsCollector("ce", {"cost_and_usage": ("get_cost_and_usage", {"TimePeriod": {"Start": "2024-01-01", "End": "2024-02-01"}, "Granularity": "MONTHLY", "Metrics": ["UnblendedCost"]})}, regional=False),
]
