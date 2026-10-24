from fastapi import APIRouter

from app.api.v1.routes.ai_activity import router as ai_activity_router
from app.api.v1.routes.ai_settings import router as ai_settings_router
from app.api.v1.routes.audit_logs import router as audit_logs_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.availability import router as availability_router
from app.api.v1.routes.candidate_pool import router as candidate_pool_router
from app.api.v1.routes.candidate_portal import router as candidate_portal_router
from app.api.v1.routes.candidate_profiles import router as candidate_profiles_router
from app.api.v1.routes.candidates import router as candidates_router
from app.api.v1.routes.chat import router as chat_router
from app.api.v1.routes.evaluations import router as evaluations_router
from app.api.v1.routes.feedback_learning import router as feedback_learning_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.hr_decisions import router as hr_decisions_router
from app.api.v1.routes.interview_question_sets import router as interview_question_sets_router
from app.api.v1.routes.interview_questions import router as interview_questions_router
from app.api.v1.routes.interviews import router as interviews_router
from app.api.v1.routes.job_applications import router as job_applications_router
from app.api.v1.routes.job_drafts import router as job_drafts_router
from app.api.v1.routes.job_profiles import router as job_profiles_router
from app.api.v1.routes.jobs import router as jobs_router
from app.api.v1.routes.observability import router as observability_router
from app.api.v1.routes.resumes import router as resumes_router
from app.api.v1.routes.screening_batches import router as screening_batches_router
from app.api.v1.routes.users import router as users_router
from app.api.v1.routes.workflows import router as workflows_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(audit_logs_router, tags=["audit-logs"])
api_router.include_router(users_router, tags=["users"])
api_router.include_router(jobs_router, tags=["jobs"])
api_router.include_router(job_drafts_router, tags=["jobs"])
api_router.include_router(job_profiles_router, tags=["job-profiles"])
api_router.include_router(candidates_router, tags=["candidates"])
api_router.include_router(candidate_pool_router, tags=["candidates"])
api_router.include_router(resumes_router, tags=["resumes"])
api_router.include_router(screening_batches_router, tags=["screening-batches"])
api_router.include_router(job_applications_router, tags=["job-applications"])
api_router.include_router(candidate_profiles_router, tags=["candidate-profiles"])
api_router.include_router(evaluations_router, tags=["evaluations"])
api_router.include_router(hr_decisions_router, tags=["hr-decisions"])
api_router.include_router(workflows_router, tags=["workflows"])
api_router.include_router(observability_router, tags=["observability"])
api_router.include_router(ai_activity_router, tags=["ai-activity"])
api_router.include_router(ai_settings_router, tags=["ai-settings"])
api_router.include_router(interviews_router, tags=["interviews"])
api_router.include_router(availability_router, tags=["availability"])
api_router.include_router(candidate_portal_router, tags=["candidate-portal"])
api_router.include_router(feedback_learning_router, tags=["feedback-learning"])
api_router.include_router(interview_questions_router, tags=["interview-questions"])
api_router.include_router(interview_question_sets_router, tags=["interview-questions"])
api_router.include_router(chat_router, tags=["chat"])
