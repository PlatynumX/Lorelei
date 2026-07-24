{
	int i;

	if (standalone == true)
		return;

	lastpolltime = controlupdatetime;

	memset(buttonpoll, 0, sizeof(buttonpoll));

	controlbuf[0] = controlbuf[1] = controlbuf[2] = 0;

	if (gamestate.autorun == 1)
		buttonpoll[bt_run] = true;

	//
	// get button states
	//
	PollKeyboardButtons();

	if (mouseenabled)
		PollMouseButtons();

	if (joystickenabled)
		PollJoystickButtons();

	//
	// get movements
	//
	if (joystickenabled)
		PollJoystickMove();

	else if (mouseenabled && MousePresent)
		PollMouseMove();

	PollKeyboardMove();

	PollMove();

	buttonbits = 0;
	if (player->flags & FL_DYING) // Player has died
	{
		if ((playerdead == true) &&
			(buttonpoll[bt_strafe] || buttonpoll[bt_attack] ||
			 buttonpoll[bt_use] ||
			 ((gamestate.battlemode == battle_Hunter) &&
			  (BATTLE_Team[player->dirchoosetime] == BATTLE_It))))
		{
			AddRespawnCommand();
		}
		memset(buttonpoll, 0, sizeof(buttonpoll));
		controlbuf[0] = controlbuf[1] = controlbuf[2] = 0;
	}

	if ((PausePressed == true) && (modemgame == false))
	{
		PausePressed = false;
		if (GamePaused == true)
			AddPauseStateCommand(COM_UNPAUSE);
		else
		{
			AddPauseStateCommand(COM_PAUSE);
		}
	}
	if (Keyboard[sc_Insert] && Keyboard[sc_X])
	{
		AddExitCommand();
	}

	for (i = (NUMTXBUTTONS - 1); i >= 0; i--)
	{
		buttonbits <<= 1;
		if (buttonpoll[i])
			buttonbits |= 1;
	}

	UpdateClientControls();
}
