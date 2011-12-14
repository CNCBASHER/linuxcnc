#ifndef EMC_TASK_HH
#define EMC_TASK_HH
#include "taskclass.hh"
extern NMLmsg *emcTaskCommand;
extern int stepping;
extern int steppingWait;
extern int emcTaskQueueCommand(NMLmsg *cmd);
extern int emcPluginCall(EMC_EXEC_PLUGIN_CALL *call_msg);
extern int emcIoPluginCall(EMC_IO_PLUGIN_CALL *call_msg);
extern int emcTaskOnce(const char *inifile);
extern int emcRunHalFiles(const char *filename);

#endif

