#include "SDL.h"

int main(int argc, char *argv[])
{
 _argc = argc;
 _argv = argv;
 ApogeePath = GetPrefDir();
 // Set which release version we're on
 gamestate.Version = ROTTVERSION;
#if (SHAREWARE == 1)
 BATTMAPS = FindFileByName(STANDARDBATTLELEVELS);
 gamestate.Product = ROTT_SHAREWARE;
#else
 BATTMAPS = FindFileByName(SITELICENSEBATTLELEVELS);
 gamestate.Product = ROTT_SITELICENSE;
 if (!BATTMAPS)
 {
 BATTMAPS = FindFileByName(SUPERROTTBATTLELEVELS);
 gamestate.Product = ROTT_SUPERCD;
 }
 if (!BATTMAPS)
 {
 BATTMAPS = FindFileByName(STANDARDBATTLELEVELS);
 gamestate.Product = ROTT_REGISTERED;
 }
#endif
 if (!BATTMAPS)
 {
 FileNotFoundError(STANDARDBATTLELEVELS);
 }
 else
 {
 char *filename;
 datadir = M_DirName(BATTMAPS);
 filename =
 M_StringJoin(datadir, PATH_SEP_STR, STANDARDGAMELEVELS, NULL);
 ROTTMAPS = M_FileCaseExists(filename);
 if (!ROTTMAPS)
 {
 FileNotFoundError(filename);
 }
 ORIG_ROTTMAPS = ROTTMAPS;
 free(filename);
 }
 PopulateEpisodeMenu(datadir);
 DrawRottTitle();
 gamestate.randomseed = -1;
 gamestate.autorun = 0;
 StartupSoftError();
 CheckCommandLineParameters();
 Z_Init(50000, 1000000);
 IN_Startup();
 InitializeGameCommands();
 if (standalone == false)
 {
 ReadConfig();
 ReadSETUPFiles();
 doublestep = 0;
 SetupWads();
 BuildTables();
 GetMenuInfo();
 }
 SetRottScreenRes(iGLOBAL_SCREENWIDTH, iGLOBAL_SCREENHEIGHT);
 if (standalone == false)
 {
 int status2 = 0;
 if (!NoSound)
 {
 status2 = SD_SetupFXCard();
 if (!status2)
 {
 SD_Startup(false);
 MU_Startup(false);
 }
 }
 Init_Tables();
 InitializeRNG();
 InitializeMessages();
 LoadColorMap();
 }
 if (standalone == true)
 ServerLoop();
 VL_SetVGAPlaneMode();
}
