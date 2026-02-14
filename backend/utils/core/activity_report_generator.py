"""
Activity Report Generator - Creates daily system status summaries.

Generates intelligent reports at scheduled times (e.g., 9:00 AM) with:
- Time-boxed metric collection
- Performance trends
- Anomaly detection summary
- Actionable recommendations
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Types of reports that can be generated."""
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_DIGEST = "weekly_digest"
    PERFORMANCE_TREND = "performance_trend"
    ANOMALY_REPORT = "anomaly_report"
    CUSTOM = "custom"


class TrendDirection(Enum):
    """Trend direction indicators."""
    IMPROVING = "improving"      # ↑
    STABLE = "stable"            # →
    DEGRADING = "degrading"      # ↓
    UNKNOWN = "unknown"          # ?


@dataclass
class MetricRecord:
    """Single metric measurement."""
    timestamp: str
    name: str
    value: float
    unit: str
    threshold: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrendMetric:
    """Metric with trend analysis."""
    name: str
    current_value: float
    previous_value: Optional[float]
    change_percent: float
    direction: TrendDirection
    unit: str
    breached_threshold: bool
    recommendation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "direction": self.direction.value
        }


@dataclass
class DailyReport:
    """Structure of a daily report."""
    id: str
    timestamp: str
    report_type: ReportType
    title: str
    summary: str
    metrics: List[Dict[str, Any]]
    trends: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    recommendations: List[str]
    highlights: Dict[str, Any]
    performance_score: float  # 0-100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "report_type": self.report_type.value,
            "title": self.title,
            "summary": self.summary,
            "metrics": self.metrics,
            "trends": self.trends,
            "anomalies": self.anomalies,
            "recommendations": self.recommendations,
            "highlights": self.highlights,
            "performance_score": self.performance_score
        }


class ActivityReportGenerator:
    """
    Generates periodic activity and system status reports.
    
    Features:
    - Scheduled report generation (cron-based)
    - Metric trend analysis
    - Anomaly detection
    - Performance scoring
    - Multi-format output (JSON, HTML, Markdown)
    """
    
    def __init__(self, metrics_provider: Optional[Any] = None):
        """
        Initialize the report generator.
        
        Args:
            metrics_provider: Optional callable/object to fetch metrics from
        """
        self.metrics_provider = metrics_provider
        self.metric_history: List[MetricRecord] = []
        self.reports_generated: List[DailyReport] = []
        self.max_reports_cached = 30  # Keep last 30 reports
        logger.info("ActivityReportGenerator initialized")
    
    def generate_daily_summary(
        self,
        metrics: Optional[Dict[str, float]] = None,
        thresholds: Optional[Dict[str, float]] = None,
        include_anomalies: bool = True
    ) -> Optional[DailyReport]:
        """
        Generate a daily summary report.
        
        Args:
            metrics: Dictionary of metric names and values
            thresholds: Dictionary of metric names and threshold values
            include_anomalies: Whether to detect and include anomalies
        
        Returns:
            DailyReport: The generated report
        """
        try:
            report_id = f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Collect metrics
            if metrics is None:
                metrics = self._collect_metrics()
            if thresholds is None:
                thresholds = self._get_default_thresholds()
            
            # Store metric history
            self._store_metrics(metrics)
            
            # Analyze trends
            trends = self._analyze_trends(metrics)
            
            # Detect anomalies
            anomalies = (
                self._detect_anomalies(metrics)
                if include_anomalies
                else []
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                metrics, trends, anomalies
            )
            
            # Calculate performance score
            performance_score = self._calculate_performance_score(metrics, thresholds)
            
            # Create highlights
            highlights = self._extract_highlights(metrics, trends, anomalies)
            
            # Build report
            report = DailyReport(
                id=report_id,
                timestamp=datetime.now().isoformat(),
                report_type=ReportType.DAILY_SUMMARY,
                title=f"Daily System Summary - {datetime.now().strftime('%B %d, %Y')}",
                summary=self._build_summary_text(metrics, performance_score),
                metrics=[self._format_metric(name, value, thresholds) for name, value in metrics.items()],
                trends=[trend.to_dict() for trend in trends],
                anomalies=anomalies,
                recommendations=recommendations,
                highlights=highlights,
                performance_score=performance_score
            )
            
            # Cache the report
            self.reports_generated.append(report)
            if len(self.reports_generated) > self.max_reports_cached:
                self.reports_generated = self.reports_generated[-self.max_reports_cached:]
            
            logger.info(f"Daily summary generated: {report_id} (score: {performance_score})")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate daily summary: {e}")
            return None
    
    def generate_performance_trend_report(
        self,
        metric_names: Optional[List[str]] = None,
        days: int = 7
    ) -> Optional[DailyReport]:
        """
        Generate a performance trend report over N days.
        
        Args:
            metric_names: Specific metrics to include. If None, uses all available
            days: Number of days to include in trend analysis
        
        Returns:
            DailyReport: The trend report
        """
        try:
            report_id = f"trend_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Filter historical metrics by date range
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_metrics = [
                m for m in self.metric_history
                if datetime.fromisoformat(m.timestamp) >= cutoff_date
            ]
            
            if not recent_metrics:
                logger.warning(f"No metrics found for last {days} days")
                return None
            
            # Calculate trend for each metric
            metric_trends = self._calculate_metric_trends(
                recent_metrics,
                metric_names
            )
            
            # Identify improving and degrading metrics
            improvements = [m for m in metric_trends if m.direction == TrendDirection.IMPROVING]
            degradations = [m for m in metric_trends if m.direction == TrendDirection.DEGRADING]
            
            recommendations = []
            if degradations:
                recommendations.extend([
                    f"⚠️ {m.name} is degrading. {m.recommendation or 'Investigate further.'}"
                    for m in degradations
                ])
            if improvements:
                recommendations.extend([
                    f"✨ {m.name} showing improvement trend"
                    for m in improvements[:3]  # Top 3
                ])
            
            # Create report
            report = DailyReport(
                id=report_id,
                timestamp=datetime.now().isoformat(),
                report_type=ReportType.PERFORMANCE_TREND,
                title=f"{days}-Day Performance Trend Report",
                summary=self._build_trend_summary(metric_trends, days),
                metrics=self._get_latest_metrics(metric_names),
                trends=[m.to_dict() for m in metric_trends],
                anomalies=[],
                recommendations=recommendations,
                highlights={
                    "improving_metrics": len(improvements),
                    "degrading_metrics": len(degradations),
                    "stable_metrics": len([m for m in metric_trends if m.direction == TrendDirection.STABLE]),
                    "best_performer": max(metric_trends, key=lambda m: m.value).name if metric_trends else None,
                    "worst_performer": min(metric_trends, key=lambda m: m.value).name if metric_trends else None
                },
                performance_score=self._calculate_trend_score(metric_trends)
            )
            
            self.reports_generated.append(report)
            logger.info(f"Performance trend report generated: {report_id}")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate trend report: {e}")
            return None
    
    def generate_anomaly_report(
        self,
        metric_names: Optional[List[str]] = None
    ) -> Optional[DailyReport]:
        """
        Generate a report focused on detected anomalies.
        
        Args:
            metric_names: Specific metrics to check for anomalies
        
        Returns:
            DailyReport: The anomaly report
        """
        try:
            report_id = f"anomaly_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Get current metrics
            metrics = self._collect_metrics()
            
            # Detect anomalies
            anomalies = self._detect_anomalies(metrics, metric_names)
            
            if not anomalies:
                logger.info("No anomalies detected")
                return None
            
            # Categorize anomalies
            critical_anomalies = [a for a in anomalies if a.get("severity") == "critical"]
            warning_anomalies = [a for a in anomalies if a.get("severity") == "warning"]
            
            # Generate remediation steps
            recommendations = []
            for anomaly in critical_anomalies[:5]:  # Top 5 critical
                recommendations.append(
                    f"🔴 {anomaly['metric']}: {anomaly['description']} - "
                    f"Action: {anomaly.get('suggestion', 'Investigate immediately')}"
                )
            
            report = DailyReport(
                id=report_id,
                timestamp=datetime.now().isoformat(),
                report_type=ReportType.ANOMALY_REPORT,
                title="Anomaly Detection Report",
                summary=f"Detected {len(anomalies)} anomalies "
                        f"({len(critical_anomalies)} critical, {len(warning_anomalies)} warnings)",
                metrics=[self._format_metric(name, value) for name, value in metrics.items()],
                trends=[],
                anomalies=anomalies,
                recommendations=recommendations,
                highlights={
                    "total_anomalies": len(anomalies),
                    "critical_count": len(critical_anomalies),
                    "warning_count": len(warning_anomalies),
                    "flagged_metrics": [a["metric"] for a in critical_anomalies]
                },
                performance_score=max(0, 100 - (len(critical_anomalies) * 20))  # Score based on anomalies
            )
            
            self.reports_generated.append(report)
            logger.info(f"Anomaly report generated: {report_id}")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate anomaly report: {e}")
            return None
    
    # ==================== Report Formatting ====================
    
    def format_report_as_markdown(self, report: DailyReport) -> str:
        """Format a report as Markdown."""
        lines = [
            f"# {report.title}",
            f"_Generated: {report.timestamp}_",
            "",
            f"## Performance Score: {report.performance_score:.1f}/100",
            "",
            "## Summary",
            report.summary,
            ""
        ]
        
        if report.recommendations:
            lines.extend([
                "## Recommendations",
                *[f"- {r}" for r in report.recommendations],
                ""
            ])
        
        if report.metrics:
            lines.extend([
                "## Metrics",
                "| Metric | Value | Status |",
                "|--------|-------|--------|"
            ])
            for metric in report.metrics:
                status = "⚠️" if metric.get("breach") else "✓"
                lines.append(
                    f"| {metric['name']} | {metric['value']} {metric['unit']} | {status} |"
                )
            lines.append("")
        
        if report.trends:
            lines.extend([
                "## Trends",
                *[f"- {t['name']}: {t['direction']} ({t['change_percent']:.1f}%)" for t in report.trends],
                ""
            ])
        
        if report.anomalies:
            lines.extend([
                "## Anomalies",
                *[f"- {a.get('metric')}: {a.get('description', 'Unknown anomaly')}" for a in report.anomalies],
                ""
            ])
        
        return "\n".join(lines)
    
    def format_report_as_html(self, report: DailyReport) -> str:
        """Format a report as HTML."""
        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "  <meta charset='UTF-8'>",
            "  <style>",
            "    body { font-family: Arial, sans-serif; margin: 20px; color: #333; }",
            "    h1 { color: #1f2937; border-bottom: 3px solid #3b82f6; padding-bottom: 10px; }",
            "    .score { font-size: 36px; font-weight: bold; color: #10b981; }",
            "    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }",
            "    .metric-card { border: 1px solid #e5e7eb; padding: 15px; border-radius: 8px; background: #f9fafb; }",
            "    .metric-value { font-size: 24px; font-weight: bold; color: #1f2937; }",
            "    .metric-name { font-size: 12px; color: #6b7280; text-transform: uppercase; }",
            "    .warning { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 10px; margin: 10px 0; }",
            "    .critical { background: #fee2e2; border-left: 4px solid #ef4444; padding: 10px; margin: 10px 0; }",
            "    .success { background: #ecfdf5; border-left: 4px solid #10b981; padding: 10px; margin: 10px 0; }",
            "  </style>",
            "</head>",
            "<body>",
            f"  <h1>{report.title}</h1>",
            f"  <p><em>Generated: {report.timestamp}</em></p>",
            f"  <div style='margin: 20px 0;'>Performance Score: <span class='score'>{report.performance_score:.0f}/100</span></div>",
            f"  <h2>Summary</h2>",
            f"  <p>{report.summary}</p>"
        ]
        
        if report.metrics:
            html_lines.extend([
                "  <h2>Metrics</h2>",
                "  <div class='metric-grid'>"
            ])
            for metric in report.metrics:
                status_class = "warning" if metric.get("breach") else "success"
                html_lines.append(
                    f"    <div class='metric-card {status_class}'>"
                    f"      <div class='metric-name'>{metric['name']}</div>"
                    f"      <div class='metric-value'>{metric['value']}</div>"
                    f"      <div class='metric-unit'>{metric['unit']}</div>"
                    f"    </div>"
                )
            html_lines.append("  </div>")
        
        if report.recommendations:
            html_lines.extend([
                "  <h2>Recommendations</h2>",
                "  <ul>"
            ])
            for rec in report.recommendations:
                html_lines.append(f"    <li>{rec}</li>")
            html_lines.extend(["  </ul>"])
        
        html_lines.extend([
            "</body>",
            "</html>"
        ])
        
        return "\n".join(html_lines)
    
    # ==================== Internal Analysis Methods ====================
    
    def _collect_metrics(self) -> Dict[str, float]:
        """Collect current system metrics."""
        if self.metrics_provider:
            try:
                return self.metrics_provider()
            except Exception as e:
                logger.error(f"Failed to collect metrics: {e}")
        
        # Return dummy metrics if no provider
        return {
            "cpu_usage": 45.2,
            "memory_usage": 62.5,
            "disk_usage": 78.1,
            "network_latency": 25.5,
            "error_rate": 0.1
        }
    
    def _store_metrics(self, metrics: Dict[str, float]) -> None:
        """Store metrics in history."""
        timestamp = datetime.now().isoformat()
        for name, value in metrics.items():
            record = MetricRecord(
                timestamp=timestamp,
                name=name,
                value=value,
                unit=self._get_unit_for_metric(name)
            )
            self.metric_history.append(record)
    
    def _analyze_trends(self, metrics: Dict[str, float]) -> List[TrendMetric]:
        """Analyze trends for metrics."""
        trends = []
        
        for name, current in metrics.items():
            # Find previous values
            metric_records = [m for m in self.metric_history if m.name == name]
            if len(metric_records) < 2:
                previous = None
                change_percent = 0.0
            else:
                previous = metric_records[-2].value
                change_percent = ((current - previous) / previous * 100) if previous != 0 else 0
            
            # Determine direction
            if previous is None:
                direction = TrendDirection.UNKNOWN
            elif abs(change_percent) < 2:
                direction = TrendDirection.STABLE
            elif change_percent > 0:
                direction = TrendDirection.DEGRADING  # Most metrics degrading = increasing
            else:
                direction = TrendDirection.IMPROVING
            
            trend = TrendMetric(
                name=name,
                current_value=current,
                previous_value=previous,
                change_percent=change_percent,
                direction=direction,
                unit=self._get_unit_for_metric(name),
                breached_threshold=False,  # Would check against thresholds
                recommendation=None
            )
            trends.append(trend)
        
        return trends
    
    def _detect_anomalies(
        self,
        metrics: Dict[str, float],
        metric_names: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in metrics."""
        anomalies = []
        
        for name, value in metrics.items():
            if metric_names and name not in metric_names:
                continue
            
            # Simple threshold-based anomaly detection
            threshold = self._get_anomaly_threshold(name)
            if value > threshold:
                severity = "critical" if value > threshold * 1.5 else "warning"
                anomalies.append({
                    "metric": name,
                    "value": value,
                    "threshold": threshold,
                    "severity": severity,
                    "description": f"{name} exceeded threshold ({value} > {threshold})",
                    "suggestion": f"Check {name} immediately"
                })
        
        return anomalies
    
    def _calculate_metric_trends(
        self,
        metric_records: List[MetricRecord],
        metric_names: Optional[List[str]] = None
    ) -> List[TrendMetric]:
        """Calculate trends from historical metric records."""
        trends = []
        grouped = {}
        
        # Group by metric name
        for record in metric_records:
            if metric_names and record.name not in metric_names:
                continue
            if record.name not in grouped:
                grouped[record.name] = []
            grouped[record.name].append(record)
        
        # Calculate trends
        for name, records in grouped.items():
            if len(records) < 2:
                continue
            
            values = [r.value for r in sorted(records, key=lambda x: x.timestamp)]
            current = values[-1]
            previous = values[-2] if len(values) > 1 else values[0]
            
            change = ((current - previous) / previous * 100) if previous != 0 else 0
            
            direction = TrendDirection.STABLE
            if abs(change) > 5:
                direction = TrendDirection.DEGRADING if change > 0 else TrendDirection.IMPROVING
            
            trend = TrendMetric(
                name=name,
                current_value=current,
                previous_value=previous,
                change_percent=change,
                direction=direction,
                unit=records[0].unit,
                breached_threshold=current > (records[0].threshold or float('inf')),
                recommendation=None
            )
            trends.append(trend)
        
        return trends
    
    def _generate_recommendations(
        self,
        metrics: Dict[str, float],
        trends: List[TrendMetric],
        anomalies: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Recommendation based on anomalies
        if anomalies:
            for anomaly in anomalies[:3]:
                recommendations.append(
                    f"⚠️ {anomaly['metric']} is {anomaly['description'].lower()}"
                )
        
        # Recommendation based on trends
        degrading_trends = [t for t in trends if t.direction == TrendDirection.DEGRADING]
        if degrading_trends:
            for trend in degrading_trends[:2]:
                recommendations.append(
                    f"📈 {trend.name} is increasing ({trend.change_percent:.1f}%). Monitor closely."
                )
        
        # If no specific issues
        if not recommendations:
            recommendations.append("✨ System operating normally.")
        
        return recommendations
    
    def _calculate_performance_score(
        self,
        metrics: Dict[str, float],
        thresholds: Dict[str, float]
    ) -> float:
        """Calculate an overall performance score (0-100)."""
        breaches = 0
        for name, value in metrics.items():
            threshold = thresholds.get(name, float('inf'))
            if value > threshold:
                breaches += 1
        
        penalty = breaches * 15  # 15 points per breach
        return max(0, 100 - penalty)
    
    def _calculate_trend_score(self, trends: List[TrendMetric]) -> float:
        """Calculate score based on trends."""
        improving = sum(1 for t in trends if t.direction == TrendDirection.IMPROVING)
        degrading = sum(1 for t in trends if t.direction == TrendDirection.DEGRADING)
        stable = sum(1 for t in trends if t.direction == TrendDirection.STABLE)
        
        total = len(trends) or 1
        return (improving * 10 + stable * 5 - degrading * 10) / total
    
    def _extract_highlights(
        self,
        metrics: Dict[str, float],
        trends: List[TrendMetric],
        anomalies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract key highlights for the report."""
        return {
            "highest_metric": max(metrics.items(), key=lambda x: x[1])[0] if metrics else None,
            "lowest_metric": min(metrics.items(), key=lambda x: x[1])[0] if metrics else None,
            "anomaly_count": len(anomalies),
            "improving_metrics": sum(1 for t in trends if t.direction == TrendDirection.IMPROVING),
            "degrading_metrics": sum(1 for t in trends if t.direction == TrendDirection.DEGRADING)
        }
    
    def _build_summary_text(self, metrics: Dict[str, float], score: float) -> str:
        """Build a natural language summary."""
        if score >= 80:
            status = "💚 Excellent"
            description = "System is operating very well with good performance across all metrics"
        elif score >= 60:
            status = "💛 Good"
            description = "System is operating well with minor issues"
        elif score >= 40:
            status = "🟠 Fair"
            description = "System has some performance issues that need attention"
        else:
            status = "❌ Poor"
            description = "System has significant issues requiring immediate attention"
        
        return f"{status}: {description}. Performance score: {score:.1f}/100"
    
    def _build_trend_summary(self, trends: List[TrendMetric], days: int) -> str:
        """Build a summary of trend data."""
        improving = sum(1 for t in trends if t.direction == TrendDirection.IMPROVING)
        degrading = sum(1 for t in trends if t.direction == TrendDirection.DEGRADING)
        
        return f"Over the last {days} days: {improving} metrics improving, {degrading} degrading"
    
    def _get_latest_metrics(self, metric_names: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Get latest metric values."""
        latest = {}
        
        for record in sorted(self.metric_history, key=lambda x: x.timestamp, reverse=True):
            if metric_names and record.name not in metric_names:
                continue
            if record.name not in latest:
                latest[record.name] = {
                    "name": record.name,
                    "value": record.value,
                    "unit": record.unit,
                    "timestamp": record.timestamp
                }
        
        return list(latest.values())
    
    @staticmethod
    def _format_metric(
        name: str,
        value: float,
        thresholds: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Format a metric for output."""
        threshold = thresholds.get(name) if thresholds else None
        breach = threshold is not None and value > threshold
        
        return {
            "name": name.replace("_", " ").title(),
            "value": f"{value:.1f}",
            "unit": ActivityReportGenerator._get_unit_for_metric(name),
            "threshold": threshold,
            "breach": breach
        }
    
    @staticmethod
    def _get_unit_for_metric(metric_name: str) -> str:
        """Get the unit for a metric."""
        units = {
            "cpu": "%",
            "memory": "%",
            "disk": "%",
            "latency": "ms",
            "error_rate": "%",
            "requests": "req/s"
        }
        
        for key, unit in units.items():
            if key in metric_name.lower():
                return unit
        return ""
    
    @staticmethod
    def _get_anomaly_threshold(metric_name: str) -> float:
        """Get anomaly threshold for a metric."""
        thresholds = {
            "cpu_usage": 90.0,
            "memory_usage": 85.0,
            "disk_usage": 95.0,
            "error_rate": 5.0,
            "network_latency": 100.0
        }
        return thresholds.get(metric_name, 90.0)
    
    @staticmethod
    def _get_default_thresholds() -> Dict[str, float]:
        """Get default thresholds for common metrics."""
        return {
            "cpu_usage": 80.0,
            "memory_usage": 80.0,
            "disk_usage": 90.0,
            "error_rate": 2.0,
            "network_latency": 50.0
        }


# Global instance
_report_generator = None


def get_activity_report_generator() -> ActivityReportGenerator:
    """Get or create the global report generator instance."""
    global _report_generator
    if _report_generator is None:
        _report_generator = ActivityReportGenerator()
    return _report_generator
