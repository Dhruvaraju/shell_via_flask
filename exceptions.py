class Job_not_found(Exception):
    """
    To be invoked when a process is not found.
    """

class Job_still_running(Exception):
    """
    To be raised when a job is still in running state
    """