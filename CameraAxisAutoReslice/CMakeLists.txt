set(MODULE_NAME CameraAxisAutoReslice)

set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  )

