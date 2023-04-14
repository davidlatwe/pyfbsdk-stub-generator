from __future__ import annotations

from ..doc_bases import Argument, Function

import pyfbsdk

class ShowToolByName(Function):
    """This function will show a specific tool in the GUI.
    ### Parameters:
        - ToolName: The name of the tool as shown in the Open Reality menu.
        - bResizeWnd: Adjust the size of the tool window if needed (if started too close to the end of the screen for example).

    ### Returns:
    A pointer to the FBTool object, `None` otherwise."""

    Arguments = (
        Argument("ToolName", str),
        Argument("bResizeWnd", bool, False),
    )

    ReturnType = pyfbsdk.FBTool
