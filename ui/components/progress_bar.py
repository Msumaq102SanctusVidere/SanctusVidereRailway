import streamlit as st
import time
from api_client import get_job_status

def progress_indicator(job_id):
    """
    Polls the /job-status endpoint every second,
    updates a progress bar and status messages,
    and returns the final job dict when done.
    """
    # Placeholders for the progress bar and messages
    prog = st.progress(0)
    msg_box = st.empty()

    while True:
        job = get_job_status(job_id)
        percent = job.get("progress", 0)
        prog.progress(percent)  # update the bar

        # Show the last few messages
        messages = job.get("progress_messages", [])
        msg_box.text("\n".join(messages[-5:]))

        # When the job is finished (or failed), return the full job info
        if job.get("status") in ("completed", "failed"):
            return job

        time.sleep(1)
