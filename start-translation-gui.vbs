Option Explicit

Dim fso, shell, repository, pythonw, command

Function UnicodeText(hexValues)
  Dim values, index, result
  values = Split(hexValues, ",")
  result = ""
  For index = 0 To UBound(values)
    result = result & ChrW(CLng("&H" & values(index)))
  Next
  UnicodeText = result
End Function

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

repository = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = fso.BuildPath(repository, ".venv\Scripts\pythonw.exe")

If Not fso.FileExists(pythonw) Then
  MsgBox UnicodeText("0050,0079,0074,0068,006F,006E,4EEE,60F3,74B0,5883,304C,898B,3064,304B,308A,307E,305B,3093,3002,0052,0045,0041,0044,004D,0045,306E,521D,56DE,30BB,30C3,30C8,30A2,30C3,30D7,3092,5B9F,884C,3057,3066,304F,3060,3055,3044,3002"), vbCritical, UnicodeText("7FFB,8A33,8A18,4E8B,30D1,30A4,30D7,30E9,30A4,30F3")
  WScript.Quit 1
End If

shell.CurrentDirectory = repository
command = Chr(34) & pythonw & Chr(34) & " -m translation_pipeline.gui"
' pythonw.exe has no console, so normal window style shows only the GUI.
shell.Run command, 1, False
