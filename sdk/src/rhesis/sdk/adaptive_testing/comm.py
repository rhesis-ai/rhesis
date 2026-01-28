import json
import logging
import time

log = logging.getLogger(__name__)


class JupyterComm:
    def __init__(self, target_name, callback=None, mode="register"):
        from ipykernel.comm import Comm

        self.target_name = target_name
        self.callback = callback
        self.jcomm = None
        if mode == "register":

            def comm_opened(comm, open_msg):
                self.jcomm = comm
                self.jcomm.on_msg(self._fire_callback)

            get_ipython().kernel.comm_manager.register_target(self.target_name, comm_opened)  # noqa: F821
        elif mode == "open":
            self.jcomm = Comm(target_name=target_name)
            self.jcomm.on_msg(self._fire_callback)
        else:
            raise Exception("Passed mode must be either 'open' or 'register'!")

    def _fire_callback(self, msg):
        self.callback(msg["content"]["data"])

    def send(self, data):
        for _ in range(10):
            if self.jcomm is None:
                time.sleep(0.5)
            else:
                self.jcomm.send(
                    {"data": json.dumps(data)}
                )  # we encode the JSON so iPython doesn't mess it up
                return
        raise Exception(
            "The Jupyter comm channel was never opened from the other side, "
            "so no message can be sent!"
        )
