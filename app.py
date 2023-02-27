from flask import Flask, request, make_response, jsonify
from flask_executor import Executor
from flask_executor.futures import Future
from typing import Optional
from http import HTTPStatus
import logging
import uuid
import time
import subprocess

from exceptions import Job_not_found, Job_still_running

def create_app():
    app = Flask(__name__)
    executor = Executor(app)
    app.config["EXECUTOR_TYPE"]='thread'
    app.config["EXECUTOR_MAX_WORKERS"]=5
    logger = logging.getLogger("terminal_via_flask")
    logging.basicConfig(filename='app.log', level=logging.DEBUG, format=f'%(asctime)s - %(name)s - %(levelname)s %(threadName)s : %(message)s')

    @app.route("/commands", methods=["POST"])
    def add_command_to_queue():
        logger.info("Command addition initiated to queue")
        key = str(uuid.uuid4())

        if(request.is_json):
            cmd = request.json.get("command")
            timeout = request.json.get("timeout")
            future: Future = executor.submit_stored(
                future_key=key,
                fn=execute_job,
                command_to_execute=cmd,
                timeout=timeout,
                key=key
            )
            return make_response(
                jsonify(
                status = "running",
                key= key
                ),
                HTTPStatus.OK
            )

    @app.route('/commands', methods=['GET'])
    def status_of_job():
        try:
            key = request.args.get("key")
            logger.info(f"Process status request being made for : {key}")
            future: Future = executor.futures._futures.get(key)

            if not future:
                raise Job_not_found(f"No job found for key {key}")
            if not future.done():
                raise Job_still_running()
        
        except Job_not_found as ex:
            logger.error(ex)
            return make_response(jsonify(error=str(ex)), HTTPStatus.NOT_FOUND)
        except Job_still_running:
            logger.debug(f"Job: '{key}' --> is still running.")
            return make_response(
                jsonify(
                statue = "running",
                key=key
                ),
                HTTPStatus.OK
            )
        except Exception as ex:
            logger.error("Error occured while processing request")
            logger.error(ex)
            return make_response(
                jsonify(
                error = str(ex)
                ),
                HTTPStatus.BAD_REQUEST
            )
        executor.futures.pop(key)
        return jsonify(future.result())


    def execute_job(command_to_execute, timeout, key):
        logger.info("command execution initiated for key:" + key)
        start_time: float = time.time()
        process_output: Optional[str] = None
        process_err: Optional[str] = None
        returncode: int = 0
        process = subprocess.Popen(
            command_to_execute,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            outs, errs = process.communicate(timeout=int(timeout))
            process_output = outs.decode("utf-8")
            process_err = errs.decode("utf-8")
            returncode = process.returncode


        except subprocess.TimeoutExpired:
            process.kill()
            process_output, _ = [s.decode("utf-8") for s in process.communicate()]
            process_err = f"command timed out after {timeout} seconds."
            returncode = process.returncode
            logger.error(f"Job: '{key}' --> failed with reason : \"{process_err}\".")

        except Exception as ex:
            process.kill()
            returncode = -1
            process_output = None
            process_err = str(ex)
            logger.error(f"Job: '{key}' --> failed with reason : \"{process_err}\".")

        end_time: float = time.time()
        process_time = end_time - start_time
        return dict(
            key=key,
            report=process_output,
            error=process_err,
            returncode=returncode,
            start_time=start_time,
            end_time=end_time,
            process_time=process_time
        )

    return app
