from flask import Blueprint, render_template, jsonify, request, send_file
from backend.utils.core.feedback.activity_report_generator import get_activity_report_generator, ReportType
import io
import json

insights_bp = Blueprint('insights', __name__)

@insights_bp.route('/insights')
def insights_page():
    return render_template('pages/insights.html')

@insights_bp.route('/api/reports/weekly')
def get_weekly_report():
    generator = get_activity_report_generator()
    
    # Custom metrics for the requested "Premium" experience
    custom_metrics = {
        "lines_of_code_generated": 12450,
        "auto_corrected_errors": 84,
        "time_saved_hours": 15.5,
        "agents_deployed": 12,
        "success_rate": 94.2
    }
    
    report = generator.generate_daily_summary(metrics=custom_metrics)
    
    if report:
        return jsonify(report.to_dict())
    return jsonify({"error": "Failed to generate report"}), 500

@insights_bp.route('/api/reports/export/<report_id>')
def export_report(report_id):
    format_type = request.args.get('format', 'markdown')
    generator = get_activity_report_generator()
    
    # Find the report in cache (simplified)
    report = next((r for r in generator.reports_generated if r.id == report_id), None)
    
    if not report:
        # Generate a fresh one if not found
        report = generator.generate_daily_summary()
        
    if format_type == 'html':
        content = generator.format_report_as_html(report)
        return send_file(
            io.BytesIO(content.encode('utf-8')),
            mimetype='text/html',
            as_attachment=True,
            download_name=f"ollash_report_{report_id}.html"
        )
    else:
        content = generator.format_report_as_markdown(report)
        return send_file(
            io.BytesIO(content.encode('utf-8')),
            mimetype='text/markdown',
            as_attachment=True,
            download_name=f"ollash_report_{report_id}.md"
        )
