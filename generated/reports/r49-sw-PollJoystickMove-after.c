{
   int joyx;
   int joyy;
   rott64_n64_gamepad_axes(&joyx, &joyy);
   JX = ((-joyx) * KEYBOARDNORMALTURNAMOUNT) / 127;
   JY = (joyy * BASEMOVE) / 127;
   if (JX != 0)
      turnheldtime += tics;
   else
      turnheldtime = 0;
   if (buttonpoll[bt_run])
      {
      JX <<= 1;
      JY <<= 1;
      }
   }
