{
	int joyx, joyy;

	INL_GetJoyDelta(joystickport, &joyx, &joyy);
	if (joypadenabled)
	{
		if (joyx >= threshold)
		{
			buttonpoll[di_east] = true;
		}
		if (-joyx >= threshold)
		{
			buttonpoll[di_west] = true;
		}
		if (joyy >= threshold)
		{
			buttonpoll[di_south] = true;
		}
		if (-joyy >= threshold)
		{
			buttonpoll[di_north] = true;
		}
	}
	else
	{
		if ((abs(joyx)) >= threshold)
		{
			JX = ((-joyx) << 13) + ((-joyx) << 11);
			turnheldtime += tics;
		}
		else
			JX = 0;

		if ((abs(joyy)) >= threshold)
		{
			JY = joyy << 4;
		}
		else
			JY = 0;
		if (buttonpoll[bt_run])
		{
			JX <<= 1;
			JY <<= 1;
		}
	}
}
