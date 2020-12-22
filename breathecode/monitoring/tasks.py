from django.utils import timezone
from celery import shared_task, Task
from .actions import run_app_diagnostic
from .models import Application
from breathecode.notify.actions import send_email_message, send_slack_raw
import logging

# Get an instance of a logger
logger = logging.getLogger(__name__)

class BaseTaskWithRetry(Task):
    autoretry_for = (Exception,)
    #                                           seconds
    retry_kwargs = {'max_retries': 5, 'countdown': 60 * 5 } 
    retry_backoff = True

@shared_task(bind=True, base=BaseTaskWithRetry)
def monitor_app(self,app_id):
    app = Application.objects.get(id=app_id)

    now = timezone.now()
    if app.paused_until is not None and app.paused_until > now:
        logger.debug("Ignoring application monitor because its paused")
        return True

    result = run_app_diagnostic(app)
    if result["status"] != "OPERATIONAL":

        if app.notify_email is not None:
            send_email_message("diagnostic", app.notify_email, {
                "subject": f"Errors have been found on {app.title} diagnostic",
                "details": result["details"]
            })
        if app.notify_slack_channel is not None:
            send_slack_raw("diagnostic", app.academy.slackteam.credentials.token, app.notify_slack_channel.slack_id, {
                "subject": f"Errors have been found on {app.title} diagnostic",
                **result,
            })

        return False
    
    return True