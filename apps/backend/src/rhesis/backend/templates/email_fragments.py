"""
Email template fragments for conditional content.
"""

# Text template fragments
TEXT_EXECUTION_TIME = "\n- Execution Time: {execution_time}"
TEXT_TEST_RUN_ID = "\n- Test Run ID: {test_run_id}"
TEXT_ERROR_DETAILS = "\n\nError Details:\n{error_message}"
TEXT_VIEW_RESULTS = "\n\nView Results:\n{frontend_url}/test-runs/{test_run_id}"

# HTML template fragments
HTML_EXECUTION_TIME_ROW = """
            <tr>
                <td style="padding: 8px 0; font-weight: bold;">Execution Time:</td>
                <td style="padding: 8px 0;">{execution_time}</td>
            </tr>"""

HTML_TEST_RUN_ID_ROW = """
            <tr>
                <td style="padding: 8px 0; font-weight: bold;">Test Run ID:</td>
                <td style="padding: 8px 0; font-family: monospace; font-size: 0.9em;">{test_run_id}</td>
            </tr>"""

HTML_ERROR_DETAILS_SECTION = """
    <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 8px; padding: 20px; margin-top: 20px;">
        <h3 style="color: #721c24; margin-top: 0;">Error Details</h3>
        <pre style="color: #721c24; white-space: pre-wrap; font-family: monospace; font-size: 0.9em;">{error_message}</pre>
    </div>"""

HTML_VIEW_RESULTS_SECTION = """
    <div style="text-align: center; margin: 30px 0;">
        <a href="{frontend_url}/test-runs/{test_run_id}" 
           style="background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold;">
            View Results
        </a>
    </div>""" 