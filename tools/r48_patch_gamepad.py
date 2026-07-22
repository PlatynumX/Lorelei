#!/usr/bin/env python3
from __future__ import annotations
import re, sys
from pathlib import Path
MARK="ROTT64_NATIVE_GAMEPAD_XY_ENGINE_V3_SOURCE_AWARE"
def fail(s): raise SystemExit("r48_patch_gamepad.py: "+s)

def span(t,n):
    p=re.compile(rf"(?m)^[ \t]*(?:static[ \t]+)?[^;\n]*\b{re.escape(n)}[ \t]*\([^;]*?\)[ \t\r\n]*\{{")
    h=list(p.finditer(t))
    if len(h)!=1: fail(f"expected one {n}, found {len(h)}")
    m=h[0]; op=t.find("{",m.start(),m.end()); d=0; state="c"; q=""; i=op
    while i<len(t):
        c=t[i]; x=t[i+1] if i+1<len(t) else ""
        if state=="c":
            if c=="/" and x=="*": state="b"; i+=2; continue
            if c=="/" and x=="/": state="l"; i+=2; continue
            if c in "'\"": state="s"; q=c; i+=1; continue
            if c=="{": d+=1
            elif c=="}":
                d-=1
                if d==0: return m.start(),op,i
            i+=1; continue
        if state=="b":
            if c=="*" and x=="/": state="c"; i+=2
            else: i+=1
        elif state=="l":
            if c=="\n": state="c"
            i+=1
        else:
            if c=="\\": i+=2; continue
            if c==q: state="c"
            i+=1
    fail("unterminated "+n)

def main():
    if len(sys.argv)!=2: fail("usage: patcher <generated-rott-root>")
    root=Path(sys.argv[1]).resolve()
    fs=[p for p in root.rglob("rt_playr.c") if p.is_file()]
    if len(fs)!=1: fail(f"expected one rt_playr.c, found {len(fs)}")
    path=fs[0]; text=path.read_text()
    if MARK in text: fail("already V3 patched")

    _,jo,jc=span(text,"PollJoystickMove")
    _,co,cc=span(text,"PollControls")
    oldjoy=text[jo:jc+1]; oldctl=text[co:cc+1]
    reports=root.parent/"reports"; reports.mkdir(parents=True,exist_ok=True)
    (reports/"r48-v12-PollJoystickMove-before.c").write_text(oldjoy+"\n")
    (reports/"r48-v12-PollControls-before.c").write_text(oldctl+"\n")

    for x in ("INL_GetJoyDelta","joyx","joyy","JX","JY","buttonpoll[bt_run]"):
        if x not in oldjoy: fail("actual PollJoystickMove missing "+x)
    for x in ("PollKeyboardButtons","PollMouseButtons","PollJoystickButtons","PollJoystickMove","PollMouseMove","PollKeyboardMove","PollMove"):
        if x not in oldctl: fail("actual PollControls missing "+x)

    jcalls=list(re.finditer(r"\bPollJoystickMove[ \t]*\(\s*\)[ \t]*;",oldctl))
    mcalls=list(re.finditer(r"\bPollMouseMove[ \t]*\(\s*\)[ \t]*;",oldctl))
    kcalls=list(re.finditer(r"\bPollKeyboardMove[ \t]*\(\s*\)[ \t]*;",oldctl))
    if (len(jcalls),len(mcalls),len(kcalls))!=(1,1,1):
        fail(f"actual call counts unexpected: joy={len(jcalls)} mouse={len(mcalls)} key={len(kcalls)}")

    newjoy='''{
   int joyx;
   int joyy;
   rott64_n64_gamepad_axes(&joyx, &joyy);
   JX = (-joyx) * (KEYBOARDNORMALTURNAMOUNT / 127);
   JY = joyy * (BASEMOVE / 127);
   if (JX != 0)
      turnheldtime += tics;
   else
      turnheldtime = 0;
   if (buttonpoll[bt_run])
      {
      JX <<= 1;
      JY <<= 1;
      }
   }'''
    text=text[:jo]+newjoy+text[jc+1:]
    js,_,_=span(text,"PollJoystickMove")
    text=text[:js]+f"/* {MARK}_DECL */\nextern void rott64_n64_gamepad_axes(int *turn_x, int *move_y);\n\n"+text[js:]

    _,co,cc=span(text,"PollControls"); ctl=text[co:cc+1]

    # Critical rule: replace CALL TOKENS ONLY. Never consume if/else syntax.
    ctl,nj=re.subn(r"\bPollJoystickMove[ \t]*\(\s*\)[ \t]*;",f"/* {MARK}_OLD_JOY_DISABLED */ (void)0;",ctl,count=1)
    ctl,nm=re.subn(r"\bPollMouseMove[ \t]*\(\s*\)[ \t]*;",f"/* {MARK}_MOUSE_DISABLED */ (void)0;",ctl,count=1)
    if nj!=1 or nm!=1: fail("movement call-only replacement failed")

    km=re.search(r"(?m)^(?P<i>[ \t]*)PollKeyboardMove[ \t]*\(\s*\)[ \t]*;",ctl)
    if not km: fail("no standalone PollKeyboardMove boundary")
    ind=km.group("i")
    ctl=ctl[:km.start()]+ind+f"/* {MARK}_MOVE_ALWAYS */\n"+ind+"PollJoystickMove();\n"+ctl[km.start():]

    if ctl.count("PollJoystickMove();")!=1: fail("expected one active joystick movement call")
    if "PollMouseMove();" in ctl: fail("mouse movement still active")
    if re.search(r"(?m)^[ \t]*else[ \t]+/\*",ctl): fail("detached else detected")

    text=text[:co]+ctl+text[cc+1:]
    _,co2,cc2=span(text,"PollControls")
    _,jo2,jc2=span(text,"PollJoystickMove")
    finalctl=text[co2:cc2+1]; finaljoy=text[jo2:jc2+1]
    (reports/"r48-v12-PollControls-after.c").write_text(finalctl+"\n")
    (reports/"r48-v12-PollJoystickMove-after.c").write_text(finaljoy+"\n")

    for x in ("INL_GetJoyDelta","joypadenabled","threshold"):
        if x in finaljoy: fail("desktop joystick token survived: "+x)

    path.write_text(text)
    print("PASS: inspected actual generated PollControls/PollJoystickMove")
    print("PASS: surrounding if/else syntax was never replaced")
    print("PASS: source snapshots saved before and after")
if __name__=="__main__": main()
