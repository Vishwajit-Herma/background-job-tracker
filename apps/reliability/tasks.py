import logging
from celery import shared_task

from apps.jobs.models import Job
from apps.reliability.evaluators import evaluate_all_jobs_reliability, evaluate_job_reliability
from apps.reliability.services import calculate_job_baseline

logger = logging.getLogger(__name__)


@shared_task(name="reliability.evaluate_reliability")
def evaluate_reliability():
    """
    Periodic task running every minute to evaluate reliability status
    for all active jobs across active projects.
    """
    logger.info("Starting periodic reliability evaluation")
    evaluated_count = evaluate_all_jobs_reliability()
    logger.info("Completed reliability evaluation for %d jobs", evaluated_count)
    return evaluated_count


@shared_task(name="reliability.evaluate_single_job")
def evaluate_single_job(job_id):
    """
    Evaluates reliability for a single job asynchronously.
    """
    evaluate_job_reliability(job_id)


@shared_task(name="reliability.recalculate_single_job_baseline")
def recalculate_single_job_baseline(job_id, sample_window_days=7):
    """
    Asynchronously recalculates baseline for a single job.
    """
    try:
        job = Job.objects.get(id=job_id, is_deleted=False)
        calculate_job_baseline(job, sample_window_days=sample_window_days)
        evaluate_job_reliability(job.id)
    except Job.DoesNotExist:
        pass


@shared_task(name="reliability.recalculate_baselines")
def recalculate_baselines(sample_window_days=7):
    """
    Periodic task to recalculate statistical baselines for all active jobs.
    """
    logger.info("Starting periodic baseline recalculation")
    jobs = Job.objects.filter(
        status="active",
        is_deleted=False,
        project__status="active",
        project__is_deleted=False,
    )

    recalculated_count = 0
    for job in jobs:
        try:
            calculate_job_baseline(job, sample_window_days=sample_window_days)
            recalculated_count += 1
        except Exception as e:
            logger.exception("Failed to recalculate baseline for job %s: %s", job.id, e)

    logger.info("Completed baseline recalculation for %d jobs", recalculated_count)
    return recalculated_count
