import logging
import math

import qt
import ctk
import vtk
import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleWidget,
    ScriptedLoadableModuleLogic,
)
from slicer.util import VTKObservationMixin
from slicer.i18n import tr as _
from slicer.i18n import translate


class CameraAxisAutoReslice(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("Camera Axis Auto Reslice")
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "IGT")]
        self.parent.dependencies = ["Markups", "Cameras"]
        self.parent.contributors = ["Generated for automatic camera-axis cortical oblique reslicing"]
        self.parent.helpText = _(
            "Drive an oblique MRI slice from the selected 3D view camera. "
            "After placing one point, rotating the 3D view automatically updates the slice orientation."
        )
        self.parent.acknowledgementText = ""


class CameraAxisAutoResliceWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        self.logic = CameraAxisAutoResliceLogic()
        self.pointNode = None
        self.observedCameraNode = None
        self.observedCameraObject = None
        self.observedSliceNode = None
        self.anchorPoint = None
        self.anchorDistanceMm = 0.0
        self.currentOffsetMm = 0.0
        self._updating = False

        self.cameraUpdateTimer = qt.QTimer()
        self.cameraUpdateTimer.setSingleShot(True)
        self.cameraUpdateTimer.setInterval(30)
        self.cameraUpdateTimer.connect("timeout()", self.onCameraUpdateTimeout)

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        parametersButton = ctk.ctkCollapsibleButton()
        parametersButton.text = _("Parameters")
        self.layout.addWidget(parametersButton)
        formLayout = qt.QFormLayout(parametersButton)

        self.volumeSelector = slicer.qMRMLNodeComboBox()
        self.volumeSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.volumeSelector.selectNodeUponCreation = True
        self.volumeSelector.addEnabled = False
        self.volumeSelector.removeEnabled = False
        self.volumeSelector.noneEnabled = False
        self.volumeSelector.showHidden = False
        self.volumeSelector.setMRMLScene(slicer.mrmlScene)
        formLayout.addRow(_("MRI volume:"), self.volumeSelector)

        self.modelSelector = slicer.qMRMLNodeComboBox()
        self.modelSelector.nodeTypes = ["vtkMRMLModelNode"]
        self.modelSelector.selectNodeUponCreation = True
        self.modelSelector.addEnabled = False
        self.modelSelector.removeEnabled = False
        self.modelSelector.noneEnabled = True
        self.modelSelector.showHidden = False
        self.modelSelector.setMRMLScene(slicer.mrmlScene)
        self.modelSelector.setToolTip(_("Optional. If selected, the placed point is projected to the closest surface point."))
        formLayout.addRow(_("Surface model:"), self.modelSelector)

        self.viewSelector = slicer.qMRMLNodeComboBox()
        self.viewSelector.nodeTypes = ["vtkMRMLViewNode"]
        self.viewSelector.selectNodeUponCreation = True
        self.viewSelector.addEnabled = False
        self.viewSelector.removeEnabled = False
        self.viewSelector.noneEnabled = False
        self.viewSelector.showHidden = False
        self.viewSelector.setMRMLScene(slicer.mrmlScene)
        formLayout.addRow(_("3D view:"), self.viewSelector)

        self.sliceViewSelector = qt.QComboBox()
        self.sliceViewSelector.addItems(["Red", "Yellow", "Green"])
        self.sliceViewSelector.setCurrentText("Red")
        formLayout.addRow(_("Slice view:"), self.sliceViewSelector)

        self.offsetSlider = ctk.ctkSliderWidget()
        self.offsetSlider.minimum = -50.0
        self.offsetSlider.maximum = 50.0
        self.offsetSlider.singleStep = 0.5
        self.offsetSlider.pageStep = 5.0
        self.offsetSlider.value = 0.0
        self.offsetSlider.suffix = " mm"
        self.offsetSlider.toolTip = _("Move the slice plane along the current camera viewing axis.")
        formLayout.addRow(_("Axis offset:"), self.offsetSlider)

        self.flipAxisCheckBox = qt.QCheckBox()
        self.flipAxisCheckBox.toolTip = _("Reverse the camera viewing axis if positive offset moves opposite to expectation.")
        formLayout.addRow(_("Flip axis:"), self.flipAxisCheckBox)

        self.autoUpdateCheckBox = qt.QCheckBox()
        self.autoUpdateCheckBox.checked = True
        self.autoUpdateCheckBox.toolTip = _("When enabled, rotating the selected 3D view automatically updates the slice.")
        formLayout.addRow(_("Auto update:"), self.autoUpdateCheckBox)

        self.showPlaneCheckBox = qt.QCheckBox()
        self.showPlaneCheckBox.checked = True
        formLayout.addRow(_("Show plane:"), self.showPlaneCheckBox)

        buttonsLayout = qt.QHBoxLayout()
        self.placeButton = qt.QPushButton(_("Start slicing"))
        self.placeButton.toolTip = _("Start slicing at the current 3D view center. If a surface is selected, the center ray is projected to the surface.")
        buttonsLayout.addWidget(self.placeButton)

        self.reanchorButton = qt.QPushButton(_("Re-anchor point"))
        self.reanchorButton.toolTip = _("Recompute the anchor point from the current 3D view center.")
        buttonsLayout.addWidget(self.reanchorButton)
        formLayout.addRow(buttonsLayout)

        self.statusLabel = qt.QLabel(_("Click Start slicing to initialize from the current 3D view center."))
        self.statusLabel.wordWrap = True
        formLayout.addRow(_("Status:"), self.statusLabel)

        self.volumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onInputsChanged)
        self.modelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onModelChanged)
        self.viewSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onViewChanged)
        self.sliceViewSelector.connect("currentTextChanged(QString)", self.onInputsChanged)
        self.offsetSlider.connect("valueChanged(double)", self.onOffsetChanged)
        self.flipAxisCheckBox.connect("toggled(bool)", self.onInputsChanged)
        self.autoUpdateCheckBox.connect("toggled(bool)", self.onAutoUpdateToggled)
        self.showPlaneCheckBox.connect("toggled(bool)", self.onShowPlaneChanged)
        self.placeButton.connect("clicked()", self.onStartSlicing)
        self.reanchorButton.connect("clicked()", self.onReanchorPoint)

        self.layout.addStretch(1)
        self.observeSelectedCamera()
        self.observeSelectedSlice()

    def enter(self):
        self.observeSelectedCamera()
        self.scheduleCameraUpdate()

    def exit(self):
        self.cameraUpdateTimer.stop()

    def cleanup(self):
        self.cameraUpdateTimer.stop()
        self.removeObservers()
        self.observedCameraNode = None
        self.observedCameraObject = None
        self.observedSliceNode = None

    def onInputsChanged(self, *args):
        self.observeSelectedSlice()
        self.updateSlice(recomputeAnchor=False)

    def onModelChanged(self, *args):
        if self.anchorPoint is not None:
            self.updateAnchorFromCamera()
        self.updateSlice(recomputeAnchor=False)

    def onViewChanged(self, *args):
        self.observeSelectedCamera()
        self.updateSlice(recomputeAnchor=False)

    def onOffsetChanged(self, value):
        if not self._updating:
            self.currentOffsetMm = float(value)
        self.updateSlice(recomputeAnchor=False)

    def onShowPlaneChanged(self, visible):
        self.logic.setVisualizationVisible(visible)
        self.updateSlice(recomputeAnchor=False)

    def onAutoUpdateToggled(self, enabled):
        self.observeSelectedCamera()
        if enabled:
            self.scheduleCameraUpdate()

    def onStartSlicing(self):
        self._ensurePointNode()
        self.pointNode.RemoveAllControlPoints()
        self.currentOffsetMm = 0.0
        self.offsetSlider.value = 0.0
        self.anchorPoint = None
        self.updateAnchorFromCamera()
        self.updateSlice(recomputeAnchor=False)

    def onReanchorPoint(self):
        self.updateAnchorFromCamera()
        self.updateSlice(recomputeAnchor=False)

    def updateAnchorFromCamera(self):
        volumeNode = self.volumeSelector.currentNode()
        viewNode = self.viewSelector.currentNode()
        if not volumeNode or not viewNode:
            self.statusLabel.setText(_("Select an MRI volume and a 3D view."))
            return False

        self._ensurePointNode()
        modelNode = self.modelSelector.currentNode()
        self.anchorPoint, self.anchorDistanceMm = self.logic.anchorPointFromCameraCenter(modelNode, viewNode)

        self._updating = True
        try:
            if self.pointNode.GetNumberOfControlPoints() < 1:
                self.pointNode.AddControlPointWorld(vtk.vtkVector3d(self.anchorPoint))
            else:
                self.pointNode.SetNthControlPointPositionWorld(0, self.anchorPoint)
        finally:
            self._updating = False
        return True

    def onPointNodeModified(self, caller=None, event=None):
        if self._updating:
            return
        if not self.pointNode or self.pointNode.GetNumberOfControlPoints() < 1:
            return
        status = self.pointNode.GetNthControlPointPositionStatus(0)
        if status == slicer.vtkMRMLMarkupsNode.PositionUndefined:
            return
        self.anchorPoint = None
        self.updateSlice(recomputeAnchor=True)

    def observeSelectedCamera(self):
        if self.observedCameraNode:
            self.removeObserver(self.observedCameraNode, vtk.vtkCommand.ModifiedEvent, self.onCameraNodeModified)
            self.observedCameraNode = None
        if self.observedCameraObject:
            self.removeObserver(self.observedCameraObject, vtk.vtkCommand.ModifiedEvent, self.onCameraNodeModified)
            self.observedCameraObject = None

        viewNode = self.viewSelector.currentNode() if hasattr(self, "viewSelector") else None
        if not viewNode or not self.autoUpdateCheckBox.checked:
            return

        cameraNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)
        if not cameraNode:
            return
        self.observedCameraNode = cameraNode
        self.addObserver(cameraNode, vtk.vtkCommand.ModifiedEvent, self.onCameraNodeModified)
        if cameraNode.GetCamera():
            self.observedCameraObject = cameraNode.GetCamera()
            self.addObserver(self.observedCameraObject, vtk.vtkCommand.ModifiedEvent, self.onCameraNodeModified)

    def observeSelectedSlice(self):
        if self.observedSliceNode:
            self.removeObserver(self.observedSliceNode, vtk.vtkCommand.ModifiedEvent, self.onSliceNodeModified)
            self.observedSliceNode = None

        if not hasattr(self, "sliceViewSelector"):
            return
        layoutManager = slicer.app.layoutManager()
        sliceWidget = layoutManager.sliceWidget(self.sliceViewSelector.currentText)
        if not sliceWidget:
            return
        self.observedSliceNode = sliceWidget.mrmlSliceNode()
        self.addObserver(self.observedSliceNode, vtk.vtkCommand.ModifiedEvent, self.onSliceNodeModified)

    def onSliceNodeModified(self, caller=None, event=None):
        if self._updating or self.anchorPoint is None:
            return
        viewNode = self.viewSelector.currentNode()
        if not viewNode:
            return
        try:
            viewAxis, _ = self.logic.cameraAxisAndTransverse(viewNode)
            depthAxis = [-viewAxis[0], -viewAxis[1], -viewAxis[2]] if self.flipAxisCheckBox.checked else viewAxis
            sliceToRAS = caller.GetSliceToRAS()
            sliceOrigin = [sliceToRAS.GetElement(0, 3), sliceToRAS.GetElement(1, 3), sliceToRAS.GetElement(2, 3)]
            delta = [
                sliceOrigin[0] - self.anchorPoint[0],
                sliceOrigin[1] - self.anchorPoint[1],
                sliceOrigin[2] - self.anchorPoint[2],
            ]
            self.currentOffsetMm = vtk.vtkMath.Dot(delta, depthAxis)
            self._updating = True
            try:
                self.offsetSlider.value = self.currentOffsetMm
            finally:
                self._updating = False
        except Exception:
            self._updating = False
            logging.debug("Failed to synchronize current slice depth from slice node.", exc_info=True)

    def onCameraNodeModified(self, caller=None, event=None):
        if self._updating or not self.autoUpdateCheckBox.checked:
            return
        self.scheduleCameraUpdate()

    def scheduleCameraUpdate(self):
        if not self.cameraUpdateTimer.isActive():
            self.cameraUpdateTimer.start()

    def onCameraUpdateTimeout(self):
        self.updateSlice(recomputeAnchor=False)

    def updateSlice(self, recomputeAnchor=False):
        if self._updating:
            return
        volumeNode = self.volumeSelector.currentNode()
        viewNode = self.viewSelector.currentNode()
        if not volumeNode or not viewNode:
            self.statusLabel.setText(_("Select an MRI volume and a 3D view."))
            return
        if self.anchorPoint is None and (not self.pointNode or self.pointNode.GetNumberOfControlPoints() < 1):
            self.statusLabel.setText(_("Click Start slicing to initialize from the current 3D view center."))
            return

        self._updating = True
        try:
            if recomputeAnchor or self.anchorPoint is None:
                if self.pointNode and self.pointNode.GetNumberOfControlPoints() > 0:
                    clickedPoint = [0.0, 0.0, 0.0]
                    self.pointNode.GetNthControlPointPositionWorld(0, clickedPoint)
                    modelNode = self.modelSelector.currentNode()
                    if modelNode:
                        self.anchorPoint, self.anchorDistanceMm = self.logic.closestPointOnModel(modelNode, clickedPoint)
                        self.pointNode.SetNthControlPointPositionWorld(0, self.anchorPoint)
                    else:
                        self.anchorPoint = list(clickedPoint)
                        self.anchorDistanceMm = 0.0
                else:
                    self._updating = False
                    if not self.updateAnchorFromCamera():
                        return
                    self._updating = True

            result = self.logic.updateSliceFromCamera(
                volumeNode=volumeNode,
                viewNode=viewNode,
                anchorPoint=self.anchorPoint,
                sliceViewName=self.sliceViewSelector.currentText,
                offsetMm=self.currentOffsetMm,
                flipAxis=bool(self.flipAxisCheckBox.checked),
                showPlane=bool(self.showPlaneCheckBox.checked),
            )
            self.statusLabel.setText(
                _("Point: ({:.2f}, {:.2f}, {:.2f}) RAS; camera axis: ({:.3f}, {:.3f}, {:.3f}); surface distance: {:.2f} mm").format(
                    result["point"][0],
                    result["point"][1],
                    result["point"][2],
                    result["axis"][0],
                    result["axis"][1],
                    result["axis"][2],
                    self.anchorDistanceMm,
                )
            )
        except Exception as exc:
            logging.exception("Failed to update automatic camera-axis reslice")
            self.statusLabel.setText(str(exc))
        finally:
            self._updating = False

    def _ensurePointNode(self):
        if self.pointNode and slicer.mrmlScene.GetNodeByID(self.pointNode.GetID()):
            return
        self.pointNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "CameraAxisAutoReslice_Point")
        self.pointNode.SetMaximumNumberOfControlPoints(1)
        self.pointNode.CreateDefaultDisplayNodes()
        displayNode = self.pointNode.GetDisplayNode()
        if displayNode:
            displayNode.SetSelectedColor(1.0, 0.75, 0.0)
        self.addObserver(self.pointNode, vtk.vtkCommand.ModifiedEvent, self.onPointNodeModified)


class CameraAxisAutoResliceLogic(ScriptedLoadableModuleLogic):
    def updateSliceFromCamera(
        self,
        volumeNode,
        viewNode,
        anchorPoint,
        sliceViewName="Red",
        offsetMm=0.0,
        flipAxis=False,
        showPlane=True,
    ):
        viewAxis, transverse = self.cameraAxisAndTransverse(viewNode)
        depthAxis = [-viewAxis[0], -viewAxis[1], -viewAxis[2]] if flipAxis else viewAxis

        # Slicer's slice view uses the slice normal and transverse axis to derive
        # the displayed vertical direction. Using the opposite of the camera view
        # axis keeps the slice view's up direction aligned with the 3D pial view.
        sliceNormal = [-viewAxis[0], -viewAxis[1], -viewAxis[2]]

        planePoint = [
            anchorPoint[0] + offsetMm * depthAxis[0],
            anchorPoint[1] + offsetMm * depthAxis[1],
            anchorPoint[2] + offsetMm * depthAxis[2],
        ]

        self.setSlicePlane(volumeNode, sliceViewName, planePoint, sliceNormal, transverse)
        if showPlane:
            self.updateVisualization(planePoint, depthAxis, transverse)
        self.setVisualizationVisible(showPlane)
        return {"point": planePoint, "axis": depthAxis}

    def cameraAxisAndTransverse(self, viewNode):
        cameraNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)
        if not cameraNode or not cameraNode.GetCamera():
            raise ValueError("Could not get active camera for the selected 3D view.")

        camera = cameraNode.GetCamera()
        position = camera.GetPosition()
        focalPoint = camera.GetFocalPoint()
        viewUp = list(camera.GetViewUp())

        axis = [
            focalPoint[0] - position[0],
            focalPoint[1] - position[1],
            focalPoint[2] - position[2],
        ]
        if vtk.vtkMath.Norm(axis) <= 0:
            raise ValueError("Selected 3D view camera has an invalid viewing direction.")
        vtk.vtkMath.Normalize(axis)

        # Match the 3D pial view orientation: screen-right is viewDirection x viewUp.
        transverse = [0.0, 0.0, 0.0]
        vtk.vtkMath.Cross(axis, viewUp, transverse)
        if vtk.vtkMath.Norm(transverse) <= 0:
            transverse = [1.0, 0.0, 0.0]
        vtk.vtkMath.Normalize(transverse)
        return axis, transverse

    def anchorPointFromCameraCenter(self, modelNode, viewNode):
        cameraNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)
        if not cameraNode or not cameraNode.GetCamera():
            raise ValueError("Could not get active camera for the selected 3D view.")

        camera = cameraNode.GetCamera()
        position = list(camera.GetPosition())
        focalPoint = list(camera.GetFocalPoint())

        axis, _ = self.cameraAxisAndTransverse(viewNode)
        if not modelNode:
            return focalPoint, 0.0

        polyData = self.getModelPolyDataInWorld(modelNode)
        if not polyData or polyData.GetNumberOfPoints() == 0 or polyData.GetNumberOfCells() == 0:
            raise ValueError("Selected surface model has no usable mesh data.")

        bounds = polyData.GetBounds()
        center = [
            0.5 * (bounds[0] + bounds[1]),
            0.5 * (bounds[2] + bounds[3]),
            0.5 * (bounds[4] + bounds[5]),
        ]
        diagonal = math.sqrt(
            (bounds[1] - bounds[0]) ** 2
            + (bounds[3] - bounds[2]) ** 2
            + (bounds[5] - bounds[4]) ** 2
        )
        cameraToCenter = math.sqrt(vtk.vtkMath.Distance2BetweenPoints(position, center))
        rayLength = max(1000.0, cameraToCenter + 4.0 * diagonal)
        rayEnd = [
            position[0] + axis[0] * rayLength,
            position[1] + axis[1] * rayLength,
            position[2] + axis[2] * rayLength,
        ]

        intersectionPoints = vtk.vtkPoints()
        cellIds = vtk.vtkIdList()
        obbTree = vtk.vtkOBBTree()
        obbTree.SetDataSet(polyData)
        obbTree.BuildLocator()
        hit = obbTree.IntersectWithLine(position, rayEnd, intersectionPoints, cellIds)
        if hit and intersectionPoints.GetNumberOfPoints() > 0:
            bestPoint = list(intersectionPoints.GetPoint(0))
            bestDistance2 = vtk.vtkMath.Distance2BetweenPoints(position, bestPoint)
            for pointIndex in range(1, intersectionPoints.GetNumberOfPoints()):
                candidate = list(intersectionPoints.GetPoint(pointIndex))
                distance2 = vtk.vtkMath.Distance2BetweenPoints(position, candidate)
                if distance2 < bestDistance2:
                    bestPoint = candidate
                    bestDistance2 = distance2
            return bestPoint, 0.0

        return self.closestPointOnModel(modelNode, focalPoint)

    def closestPointOnModel(self, modelNode, worldPoint):
        polyData = self.getModelPolyDataInWorld(modelNode)
        if not polyData or polyData.GetNumberOfPoints() == 0 or polyData.GetNumberOfCells() == 0:
            raise ValueError("Selected surface model has no usable mesh data.")

        locator = vtk.vtkCellLocator()
        locator.SetDataSet(polyData)
        locator.BuildLocator()

        closestPoint = [0.0, 0.0, 0.0]
        cellId = vtk.mutable(0)
        subId = vtk.mutable(0)
        distance2 = vtk.mutable(0.0)
        locator.FindClosestPoint(worldPoint, closestPoint, cellId, subId, distance2)
        return list(closestPoint), math.sqrt(float(distance2))

    def getModelPolyDataInWorld(self, modelNode):
        polyData = modelNode.GetPolyData()
        if polyData is None:
            return None
        parentTransformNode = modelNode.GetParentTransformNode()
        if parentTransformNode is None:
            output = vtk.vtkPolyData()
            output.DeepCopy(polyData)
            return output

        worldTransform = vtk.vtkGeneralTransform()
        parentTransformNode.GetTransformToWorld(worldTransform)
        transformFilter = vtk.vtkTransformPolyDataFilter()
        transformFilter.SetInputData(polyData)
        transformFilter.SetTransform(worldTransform)
        transformFilter.Update()
        output = vtk.vtkPolyData()
        output.DeepCopy(transformFilter.GetOutput())
        return output

    def setSlicePlane(self, volumeNode, sliceViewName, point, normal, transverse):
        layoutManager = slicer.app.layoutManager()
        sliceWidget = layoutManager.sliceWidget(sliceViewName)
        if not sliceWidget:
            raise ValueError("Slice view '{}' is not available in the current layout.".format(sliceViewName))

        sliceLogic = sliceWidget.sliceLogic()
        compositeNode = sliceLogic.GetSliceCompositeNode()
        compositeNode.SetBackgroundVolumeID(volumeNode.GetID())

        sliceNode = sliceWidget.mrmlSliceNode()
        sliceNode.SetSliceToRASByNTP(
            normal[0],
            normal[1],
            normal[2],
            transverse[0],
            transverse[1],
            transverse[2],
            point[0],
            point[1],
            point[2],
            0,
        )
        sliceNode.SetSliceVisible(True)
        sliceNode.SetSliceEdgeVisibility3D(True)
        sliceNode.UpdateMatrices()

    def updateVisualization(self, point, axis, transverse):
        scene = slicer.mrmlScene
        if not hasattr(self, "planeModelNode"):
            self.planeModelNode = None
            self.axisLineNode = None

        if self.planeModelNode is None or scene.GetNodeByID(self.planeModelNode.GetID()) is None:
            self.planeModelNode = scene.AddNewNodeByClass("vtkMRMLModelNode", "CameraAxisAutoReslice_Plane")
            displayNode = scene.AddNewNodeByClass("vtkMRMLModelDisplayNode", "CameraAxisAutoReslice_Plane_Display")
            displayNode.SetColor(0.1, 0.8, 0.4)
            displayNode.SetOpacity(0.25)
            displayNode.SetBackfaceCulling(False)
            self.planeModelNode.SetAndObserveDisplayNodeID(displayNode.GetID())

        planeSizeMm = 80.0
        secondAxis = [0.0, 0.0, 0.0]
        vtk.vtkMath.Cross(axis, transverse, secondAxis)
        vtk.vtkMath.Normalize(secondAxis)

        half = 0.5 * planeSizeMm
        points = vtk.vtkPoints()
        for s, t in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
            points.InsertNextPoint(
                point[0] + s * half * transverse[0] + t * half * secondAxis[0],
                point[1] + s * half * transverse[1] + t * half * secondAxis[1],
                point[2] + s * half * transverse[2] + t * half * secondAxis[2],
            )

        polygon = vtk.vtkPolygon()
        polygon.GetPointIds().SetNumberOfIds(4)
        for i in range(4):
            polygon.GetPointIds().SetId(i, i)
        cells = vtk.vtkCellArray()
        cells.InsertNextCell(polygon)

        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetPolys(cells)
        self.planeModelNode.SetAndObservePolyData(polyData)

        if self.axisLineNode is None or scene.GetNodeByID(self.axisLineNode.GetID()) is None:
            self.axisLineNode = scene.AddNewNodeByClass("vtkMRMLMarkupsLineNode", "CameraAxisAutoReslice_Axis")
            self.axisLineNode.CreateDefaultDisplayNodes()
            displayNode = self.axisLineNode.GetDisplayNode()
            if displayNode:
                displayNode.SetSelectedColor(1.0, 0.25, 0.0)
                displayNode.SetLineThickness(0.4)

        endPoint = [point[0] + axis[0] * 30.0, point[1] + axis[1] * 30.0, point[2] + axis[2] * 30.0]
        if self.axisLineNode.GetNumberOfControlPoints() != 2:
            self.axisLineNode.RemoveAllControlPoints()
            self.axisLineNode.AddControlPointWorld(vtk.vtkVector3d(point))
            self.axisLineNode.AddControlPointWorld(vtk.vtkVector3d(endPoint))
        else:
            self.axisLineNode.SetNthControlPointPositionWorld(0, point)
            self.axisLineNode.SetNthControlPointPositionWorld(1, endPoint)

    def setVisualizationVisible(self, visible):
        if not hasattr(self, "planeModelNode"):
            return
        for node in [self.planeModelNode, self.axisLineNode]:
            if node and node.GetDisplayNode():
                node.GetDisplayNode().SetVisibility(bool(visible))


class CameraAxisAutoResliceTest:
    pass
