from chase_helpers import test_state, get_current_environment_info, get_job_by_number, test_state
import chase_helpers

# Force Live:
chase_helpers.test_state = True
print(get_current_environment_info())  # confirm Live URL/creds
print(get_job_by_number(1, 1781))
