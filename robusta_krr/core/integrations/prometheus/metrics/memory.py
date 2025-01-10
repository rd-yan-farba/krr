from robusta_krr.core.models.objects import K8sObjectData

from .base import PrometheusMetric, QueryType


# A central definition for memory usage metric
def memory_usage_metric(namespace, pods_selector, container, cluster_label):
    container_metrics_selector = f"""
        pod=~"{pods_selector}", 
        container="{container}",
        namespace="{namespace}", 
        __cluster__="{cluster_label}\"
    """
    jvm_metrics_selector = f"""
        kubernetes_pod_name=~"{pods_selector}, 
        component="{container}, 
        namespace="{namespace}, 
        __cluster__="{cluster_label}\"
    """
    return f"""
        max(    
            max(
                max(container_memory_max_usage_bytes{{{container_metrics_selector}}}) 
                - 
                sum(jvm_memory_committed_bytes{{{jvm_metrics_selector}}})
                +
                sum(jvm_memory_used_bytes{{{jvm_metrics_selector}}})
                )
            )
        )
    """


class MemoryLoader(PrometheusMetric):
    """
    A metric loader for loading memory usage metrics.
    """

    query_type: QueryType = QueryType.QueryRange

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return memory_usage_metric(object.namespace, pods_selector, object.container, cluster_label)


class MaxMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading max memory usage metrics.
    """

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            max_over_time(
                {memory_usage_metric(object.namespace, pods_selector, object.container, cluster_label)}
                [{duration}:{step}]
            )
        """


class MemoryAmountLoader(PrometheusMetric):
    """
    A metric loader for loading memory points count.
    """

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            count_over_time(
                {memory_usage_metric(object.namespace, pods_selector, object.container, cluster_label)}
                [{duration}:{step}]
            )
        """


# TODO: Need to battle test if this one is correct.
class MaxOOMKilledMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading the maximum memory limits that were surpassed by the OOMKilled event.
    """

    warning_on_no_data = False

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            max_over_time(
                max(
                    max(
                        kube_pod_container_resource_limits{{
                            resource="memory",
                            namespace="{object.namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                            {cluster_label}
                        }} 
                    ) by (pod, container, job)
                    * on(pod, container, job) group_left(reason)
                    max(
                        kube_pod_container_status_last_terminated_reason{{
                            reason="OOMKilled",
                            namespace="{object.namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                            {cluster_label}
                        }}
                    ) by (pod, container, job, reason)
                ) by (container, pod, job)
                [{duration}:{step}]
            )
        """
