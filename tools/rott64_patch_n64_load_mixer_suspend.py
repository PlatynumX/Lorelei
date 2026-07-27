#!/usr/bin/env python3
from pathlib import Path
import re, sys
MARK_G="ROTT64_R96C_LOAD_RESTORE_MIXER_SUSPEND_FLAG"
MARK_B="ROTT64_R96C_LOAD_RESTORE_MIXER_SUSPEND_BEGIN"
MARK_E="ROTT64_R96C_LOAD_RESTORE_MIXER_SUSPEND_END"
MARK_M="ROTT64_R96C_MIXER_PUMP_SKIP_DURING_LOAD"
def die(m): raise SystemExit("ERROR: "+m)
def fn_span(t,n):
    m=re.search(r"(?m)^[A-Za-z_][A-Za-z0-9_ \t\*]*\b"+re.escape(n)+r"\s*\([^;]*?\)\s*\{",t,re.S)
    if not m: die("function not found: "+n)
    ob=t.find("{",m.start(),m.end()); d=0
    for i in range(ob,len(t)):
        if t[i]=="{": d+=1
        elif t[i]=="}":
            d-=1
            if d==0: return m.start(),ob,i
    die("closing brace not found: "+n)
def after_open(t,ob,b):
    at=ob+1
    if at<len(t) and t[at]=="\n": at+=1
    return t[:at]+b+t[at:]
def patch_game(root):
    p=root/"rt_game.c"; t=p.read_text(); o=t
    fs,ob,cb=fn_span(t,"LoadTheGame")
    if MARK_G not in t:
        g="\n".join(["/* "+MARK_G+": global flag visible to platform mixer pump. */","#ifdef __N64__","volatile int rott64_n64_load_restore_in_progress = 0;","#endif",""])
        t=t[:fs]+g+t[fs:]; fs,ob,cb=fn_span(t,"LoadTheGame")
    body=t[ob:cb]
    if MARK_B not in body:
        b="\n".join(["#ifdef __N64__","    /* "+MARK_B+" */","    rott64_n64_load_restore_in_progress = 1;","#endif",""])
        t=after_open(t,ob,b); fs,ob,cb=fn_span(t,"LoadTheGame")
    body=t[ob:cb]
    if MARK_E not in body:
        e="\n".join(["#ifdef __N64__","    /* "+MARK_E+" */","    rott64_n64_load_restore_in_progress = 0;","#endif",""])
        t=t[:cb]+e+t[cb:]
    fs,ob,cb=fn_span(t,"LoadTheGame"); body=t[ob:cb]
    if "return;" in body and "ROTT64_R96C_LOAD_RESTORE_MIXER_SUSPEND_RETURN_CLEAR" not in body:
        nb=body.replace("return;","#ifdef __N64__\n    /* ROTT64_R96C_LOAD_RESTORE_MIXER_SUSPEND_RETURN_CLEAR */\n    rott64_n64_load_restore_in_progress = 0;\n#endif\n    return;")
        t=t[:ob]+nb+t[cb:]
    for x in [MARK_G,MARK_B,MARK_E,"volatile int rott64_n64_load_restore_in_progress = 0;","rott64_n64_load_restore_in_progress = 1;","rott64_n64_load_restore_in_progress = 0;"]:
        if x not in t: die("rt_game.c missing "+x)
    if t!=o: p.write_text(t.rstrip()+"\n"); print("PASS: LoadTheGame mixer suspend flag installed")
    else: print("PASS: LoadTheGame mixer suspend flag already present")
def patch_stub():
    p=Path("platform/n64/sdl_mixer_stub.c"); t=p.read_text(); o=t
    fs,ob,cb=fn_span(t,"rott64_mixer_pump"); body=t[ob:cb]
    if MARK_M not in body:
        g="\n".join(["#ifdef __N64__","    /* "+MARK_M+" */","    extern volatile int rott64_n64_load_restore_in_progress;","    if (rott64_n64_load_restore_in_progress) {","        return;","    }","#endif",""])
        t=after_open(t,ob,g)
    fs,ob,cb=fn_span(t,"rott64_mixer_pump"); body=t[ob:cb]
    for x in [MARK_M,"extern volatile int rott64_n64_load_restore_in_progress;","if (rott64_n64_load_restore_in_progress)","return;"]:
        if x not in body: die("sdl_mixer_stub.c missing "+x)
    if "rott64_audio_pump" in body and body.find(MARK_M)>body.rfind("rott64_audio_pump"): die("mixer suspend guard after audio pump")
    if t!=o: p.write_text(t.rstrip()+"\n"); print("PASS: mixer pump load-restore suspend guard installed")
    else: print("PASS: mixer pump load-restore suspend guard already present")
def main():
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path("generated/rott")
    patch_game(root); patch_stub()
if __name__=="__main__": main()
