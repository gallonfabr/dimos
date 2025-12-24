from dimos.core import Module, In, rpc
from dimos.vr.models import ControllerData, ControllerFrame
from reactivex.disposable import Disposable


class VRControllerSubscriber(Module):
    """Subscriber module for receiving VR controller data"""

    controller_left_in: In[ControllerData] = None
    controller_right_in: In[ControllerData] = None
    controller_both_in: In[ControllerFrame] = None

    def __init__(self, **kwargs):
        """Initialize VR controller module."""
        super().__init__(**kwargs)
        self.left_state = None
        self.right_state = None

    def _has_config(self, input_port):
        """Check if input port has transport or connection configured."""
        if input_port.connection is not None:
            return True
        try:
            return input_port.transport is not None
        except AttributeError:
            return False

    @rpc
    def start(self):
        super().start()

        if self._has_config(self.controller_left_in):
            unsub = self.controller_left_in.subscribe(self.on_left_controller)
            self._disposables.add(Disposable(unsub))

        if self._has_config(self.controller_right_in):
            unsub = self.controller_right_in.subscribe(self.on_right_controller)
            self._disposables.add(Disposable(unsub))

        if self._has_config(self.controller_both_in):
            unsub = self.controller_both_in.subscribe(self.on_both_controllers)
            self._disposables.add(Disposable(unsub))

    def on_left_controller(self, data: ControllerData):
        """Callback for left controller data. Override in subclass."""
        if data.connected:
            self.left_state = data

    def on_right_controller(self, data: ControllerData):
        """Callback for right controller data. Override in subclass."""
        if data.connected:
            self.right_state = data

    def on_both_controllers(self, frame: ControllerFrame):
        """Callback for complete controller frame. Override in subclass."""
        if frame.left and frame.left.connected:
            self.left_state = frame.left
        if frame.right and frame.right.connected:
            self.right_state = frame.right
