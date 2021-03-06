/********************************************************************
* Description: command.c
*   emcmotCommandhandler() takes commands passed from user space and
*   performs various functions based on the value in emcmotCommand->command.
*   For the full list, see the EMCMOT_COMMAND enum in motion.h
*
* pc says:
*
*   Most of the configs would be better off being passed via an ioctl
*   implimentation leaving pure realtime data to be handled by
*   emcmotCommmandHandler() - This would provide a small performance
*   increase on slower systems.
*
* jmk says:
*
*   Using commands to set config parameters is "undesireable", because
*   of the large amount of code needed for each parameter.  Today you
*   need to do the following to add a single new parameter called foo:
*
*   1)  Add a member 'foo' to the config or joint structure in motion.h
*   2)  Add a command 'EMCMOT_SET_FOO" to the cmd_code_t enum in motion.h
*   3)  Add a field to the command_t struct for the value used by
*       the set command (if there isn't already one that can be used.)
*   4)  Add a case to the giant switch statement in command.c to
*       handle the 'EMCMOT_SET_FOO' command.
*   5)  Write a function emcSetFoo() in taskintf.cc to issue the command.
*   6)  Add a prototype for emcSetFoo() to emc.hh
*   7)  Add code to iniaxis.cc (or one of the other inixxx.cc files) to
*       get the value from the ini file and call emcSetFoo().  (Note
*       that each parameter has about 16 lines of code, but the code
*       is identical except for variable/parameter names.)
*   8)  Add more code to iniaxis.cc to write the new value back out
*       to the ini file.
*   After all that, you have the abililty to get a number from the
*   ini file to a structure in shared memory where the motion controller
*   can actually use it.  However, if you want to manipulate that number
*   using NML, you have to do more:
*   9)  Add a #define EMC_SET_FOO_TYPE to emc.hh
*   10) Add a class definition for EMC_SET_FOO to emc.hh
*   11) Add a case to a giant switch statement in emctaskmain.cc to
*       call emcSetFoo() when the NML command is received.  (Actually
*       there are about 6 switch statements that need at least a
*       case label added.
*   12) Add cases to two giant switch statements in emc.cc, associated
*       with looking up and formating the command.
*
*
*   Derived from a work by Fred Proctor & Will Shackleford
*
* Author:
* License: GPL Version 2
* System: Linux
*
* Copyright (c) 2004 All rights reserved.
********************************************************************/

#include <linux/types.h>
#include <float.h>
#include "posemath.h"
#include "rtapi.h"
#include "hal.h"
#include "motion.h"
#include "motion_debug.h"
#include "motion_struct.h"
#include "emcmotglb.h"
#include "mot_priv.h"
#include "rtapi_math.h"
#include "motion_types.h"
#include "stdio.h"
#include "assert.h"
#include <sync_cmd.h>
// Mark strings for translation, but defer translation to userspace
#define _(s) (s)

static int rehomeAll;

/* loops through the active joints and checks if any are not homed */
int checkAllHomed(void)
{
    int joint_num;
    emcmot_joint_t *joint;

    /* bail out if the allHomed flag is already set */
    if (0 != emcmotDebug) {
	if (emcmotDebug->allHomed) return 1;
    }

    for (joint_num = 0; joint_num < emcmotConfig->numJoints; joint_num++) {
	/* point to joint data */
	joint = &joints[joint_num];
	if (!GET_JOINT_ACTIVE_FLAG(joint)) {
	    /* if joint is not active, don't even look at its limits */
	    continue;
	}
	if (!GET_JOINT_HOMED_FLAG(joint)) {
	    /* if any of the joints is not homed return false */
	    return 0;
	}
    }
    /* set the global flag that all joints are homed */
    if (0 != emcmotDebug) {
	emcmotDebug->allHomed = 1;
    }
    /* return true if all active joints are homed*/
    return 1;
}

/* limits_ok() returns 1 if none of the hard limits are set,
   0 if any are set. Called on a linear and circular move. */
static int limits_ok(void)
{
    int joint_num;
    emcmot_joint_t *joint;

    for (joint_num = 0; joint_num < emcmotConfig->numJoints; joint_num++) {
	/* point to joint data */
	joint = &joints[joint_num];
	if (!GET_JOINT_ACTIVE_FLAG(joint)) {
	    /* if joint is not active, don't even look at its limits */
	    continue;
	}

	if (GET_JOINT_PHL_FLAG(joint) || GET_JOINT_NHL_FLAG(joint)) {
	    return 0;
	}
    }

    return 1;
}

/* check the value of the joint and velocity against current position,
   returning 1 (okay) if the request is to jog off the limit, 0 (bad)
   if the request is to jog further past a limit. */
static int jog_ok(int joint_num, double vel)
{
    emcmot_joint_t *joint;
    int neg_limit_override, pos_limit_override;

    /* point to joint data */
    joint = &joints[joint_num];
    /* are any limits for this joint overridden? */
    neg_limit_override = emcmotStatus->overrideLimitMask & ( 1 << (joint_num*2));
    pos_limit_override = emcmotStatus->overrideLimitMask & ( 2 << (joint_num*2));
    if ( neg_limit_override && pos_limit_override ) {
	/* both limits have been overridden at the same time.  This
	   happens only when they both share an input, but means it
	   is impossible to know which direction is safe to move.  So
	   we skip the following tests... */
	return 1;
    }
    if (joint_num < 0 || joint_num >= emcmotConfig->numJoints) {
	reportError(_("Can't jog invalid joint number %d."), joint_num);
	return 0;
    }
    if (vel > 0.0 && GET_JOINT_PHL_FLAG(joint)) {
	reportError(_("Can't jog joint %d further past max hard limit."),
	    joint_num);
	return 0;
    }
    if (vel < 0.0 && GET_JOINT_NHL_FLAG(joint)) {
	reportError(_("Can't jog joint %d further past min hard limit."),
	    joint_num);
	return 0;
    }
    refresh_jog_limits(joint);
    if ( vel > 0.0 && (joint->pos_cmd > joint->max_jog_limit) ) {
	reportError(_("Can't jog joint %d further past max soft limit."),
	    joint_num);
	return 0;
    }
    if ( vel < 0.0 && (joint->pos_cmd < joint->min_jog_limit) ) {
	reportError(_("Can't jog joint %d further past min soft limit."),
	    joint_num);
	return 0;
    }
    /* okay to jog */
    return 1;
}

/* Jogs limits change, based on whether the machine is homed or
   or not.  If not homed, the limits are relative to the current
   position by +/- the full range of travel.  Once homed, they
   are absolute.
*/
void refresh_jog_limits(emcmot_joint_t *joint)
{
    double range;

    if (GET_JOINT_HOMED_FLAG(joint)) {
	/* if homed, set jog limits using soft limits */
	joint->max_jog_limit = joint->max_pos_limit;
	joint->min_jog_limit = joint->min_pos_limit;
    } else {
	/* not homed, set limits based on current position */
	range = joint->max_pos_limit - joint->min_pos_limit;
	joint->max_jog_limit = joint->pos_fb + range;
	joint->min_jog_limit = joint->pos_fb - range;
    }
}

/* inRange() returns non-zero if the position lies within the joint
   limits, or 0 if not.  It also reports an error for each joint limit
   violation.  It's possible to get more than one violation per move. */
static int inRange(EmcPose pos, int id, char *move_type)
{
    double joint_pos[EMCMOT_MAX_JOINTS];
    int joint_num;
    emcmot_joint_t *joint;
    int in_range = 1;

    /* fill in all joints with 0 */
    for (joint_num = 0; joint_num < emcmotConfig->numJoints; joint_num++) {
	joint_pos[joint_num] = 0.0;
    }

    /* now fill in with real values, for joints that are used */
    kinematicsInverse(&pos, joint_pos, &iflags, &fflags);

    for (joint_num = 0; joint_num < emcmotConfig->numJoints; joint_num++) {
	/* point to joint data */
	joint = &joints[joint_num];

	if (!GET_JOINT_ACTIVE_FLAG(joint)) {
	    /* if joint is not active, don't even look at its limits */
	    continue;
	}
	if (joint_pos[joint_num] > joint->max_pos_limit) {
            in_range = 0;
	    reportError(_("%s move on line %d would exceed joint %d's positive limit"),
			move_type, id, joint_num);
        }

        if (joint_pos[joint_num] < joint->min_pos_limit) {
	    in_range = 0;
	    reportError(_("%s move on line %d would exceed joint %d's negative limit"),
			move_type, id, joint_num);
	}
    }
    return in_range;
}

/* clearHomes() will clear the homed flags for joints that have moved
   since homing, outside coordinated control, for machines with no
   forward kinematics. This is used in conjunction with the rehomeAll
   flag, which is set for any coordinated move that in general will
   result in all joints moving. The flag is consulted whenever a joint
   is jogged in joint mode, so that either its flag can be cleared if
   no other joints have moved, or all have to be cleared. */
void clearHomes(int joint_num)
{
    int n;
    emcmot_joint_t *joint;

    if (emcmotConfig->kinType == KINEMATICS_INVERSE_ONLY) {
	if (rehomeAll) {
	    for (n = 0; n < emcmotConfig->numJoints; n++) {
		/* point at joint data */
		joint = &(joints[n]);
		/* clear flag */
		SET_JOINT_HOMED_FLAG(joint, 0);
	    }
	} else {
	    /* point at joint data */
	    joint = &joints[joint_num];
	    /* clear flag */
	    SET_JOINT_HOMED_FLAG(joint, 0);
	}
    }
    if (0 != emcmotDebug) {
	emcmotDebug->allHomed = 0;
    }
}

void emcmotSetRotaryUnlock(int axis, int unlock) {

    *(emcmot_hal_data->joint[axis].unlock) = unlock;
}

int emcmotGetRotaryIsUnlocked(int axis) {
    return *(emcmot_hal_data->joint[axis].is_unlocked);
}

/*! \function emcmotDioWrite()

  sets or clears a HAL DIO pin, 
  pins get exported at runtime
  
  index is valid from 0 to emcmotConfig->num_dio <= EMCMOT_MAX_DIO, defined in emcmotcfg.h
  
*/
void emcmotDioWrite(int index, char value)
{
    if ((index >= emcmotConfig->numDIO) || (index < 0)) {
	rtapi_print_msg(RTAPI_MSG_ERR, "ERROR: index out of range, %d not in [0..%d] (increase num_dio/EMCMOT_MAX_DIO=%d)\n", index, emcmotConfig->numDIO, EMCMOT_MAX_DIO);
    } else {
	if (value != 0) {
	    *(emcmot_hal_data->synch_do[index])=1;
	} else {
	    *(emcmot_hal_data->synch_do[index])=0;
	}
    }
}


void emcmotSyncInputWrite(int index, double timeout, int wait_type)
{

    if ((index >= emcmotConfig->numSyncIn) || (index < 0)) {
        rtapi_print_msg(RTAPI_MSG_ERR, "ERROR: index out of range, %d not in [0..%d] (increase num_dio/EMCMOT_MAX_DIO=%d)\n", index, emcmotConfig->numDIO, EMCMOT_MAX_DIO);
    } else {
        //TODO-eric: be sure done in a servo interval??
/*        for (i = 0; i < emcmotConfig->numSyncIn; i++) {
            if(i != index) *(emcmot_hal_data->sync_in[i])=0;
            else {
                *(emcmot_hal_data->sync_in[i])=1;
            }
         }*/
        *(emcmot_hal_data->sync_in) = index;
        *(emcmot_hal_data->sync_wait_type) = wait_type;
        *(emcmot_hal_data->timeout) = timeout;
        *(emcmot_hal_data->sync_in_trigger) = 1;
        //printf("motmod write hal wait_type(%d) timeout(%f) pin(%d)\n",wait_type,timeout,index);
    }
}

/*! \function emcmotAioWrite()

  sets or clears a HAL AIO pin, 
  pins get exported at runtime
  
  index is valid from 0 to emcmotConfig->num_aio <= EMCMOT_MAX_AIO, defined in emcmotcfg.h
  
*/
void emcmotAioWrite(int index, double value)
{
    if ((index >= emcmotConfig->numAIO) || (index < 0)) {
	rtapi_print_msg(RTAPI_MSG_ERR, "ERROR: index out of range, %d not in [0..%d] (increase num_aio/EMCMOT_MAX_AIO=%d)\n", index, emcmotConfig->numAIO, EMCMOT_MAX_AIO);
    } else {
        *(emcmot_hal_data->analog_output[index]) = value;
    }
}

static int is_feed_type(int motion_type)
{
    switch(motion_type) {
    case EMC_MOTION_TYPE_ARC:
    case EMC_MOTION_TYPE_FEED:
    case EMC_MOTION_TYPE_PROBING:
        return 1;
    default:
        rtapi_print_msg(RTAPI_MSG_ERR, "Internal error: unhandled motion type %d\n", motion_type);
    case EMC_MOTION_TYPE_TOOLCHANGE:
    case EMC_MOTION_TYPE_TRAVERSE:
    case EMC_MOTION_TYPE_INDEXROTARY:
        return 0;
    }
}

/*
  emcmotCommandHandler() is called each main cycle to read the
  shared memory buffer
  */
void emcmotCommandHandler(void *arg, long period)
{
    int joint_num, axis_num;
    int n;
    emcmot_joint_t *joint;
    emcmot_axis_t *axis;
    double tmp1;
    emcmot_comp_entry_t *comp_entry;
    char issue_atspeed = 0;
    int msg_level_before = rtapi_get_msg_level();
    //DEBUG: int msg_level_now = msg_level_before | RTAPI_MSG_DBG;
    int msg_level_now = msg_level_before;
    static int counter = 0;
    rtapi_set_msg_level(msg_level_now);
    counter = counter+1;
    check_stuff ( "before command_handler()" );

    /* check for split read */
    if (emcmotCommand->head != emcmotCommand->tail) {
	emcmotDebug->split++;
	return;			/* not really an error */
    }
    if (emcmotCommand->commandNum != emcmotStatus->commandNumEcho) {
	/* increment head count-- we'll be modifying emcmotStatus */
	emcmotStatus->head++;
	emcmotDebug->head++;

	/* got a new command-- echo command and number... */
	emcmotStatus->commandEcho = emcmotCommand->command;
	emcmotStatus->commandNumEcho = emcmotCommand->commandNum;

	/* clear status value by default */
	emcmotStatus->commandStatus = EMCMOT_COMMAND_OK;
	
	/* ...and process command */

	/* Many commands uses "command->joint" to indicate which joint they
	   wish to operate on.  This code eliminates the need to copy
	   command->joint to "joint_num", limit check it, and then set "joint"
	   to point to the joint data.  All the individual commands need to do
	   is verify that "joint" is non-zero. */
	joint_num = emcmotCommand->joint;
	if (joint_num >= 0 && joint_num < emcmotConfig->numJoints) {
	    /* valid joint, point to it's data */
	    joint = &joints[joint_num];
	} else {
	    /* bad joint number */
	    joint = 0;
	}

        /* same for axes */
	axis_num = emcmotCommand->axis;
	if (axis_num >= 0 && axis_num < EMCMOT_MAX_AXIS) {
	    /* valid joint, point to it's data */
	    axis = &axes[axis_num];
	} else {
	    /* bad axis number */
	    axis = 0;
	}

/* printing of commands for troubleshooting */
	rtapi_print_msg(RTAPI_MSG_DBG, "%d: CMD %d, code %3d ", emcmotStatus->heartbeat,
	    emcmotCommand->commandNum, emcmotCommand->command);

	switch (emcmotCommand->command) {
	case EMCMOT_ABORT:
	    /* abort motion */
	    /* can happen at any time */
	    /* this command attempts to stop all machine motion. it looks at
	       the current mode and acts accordingly, if in teleop mode, it
	       sets the desired velocities to zero, if in coordinated mode,
	       it calls the traj planner abort function (don't know what that
	       does yet), and if in free mode, it disables the free mode traj
	       planners which stops joint motion */
	    rtapi_print_msg(RTAPI_MSG_DBG, "ABORT");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    /* check for coord or free space motion active */
	    if (GET_MOTION_TELEOP_FLAG()) {
                ZERO_EMC_POSE(emcmotDebug->teleop_data.desiredVel);
//orig:		for (axis_num = 0; axis_num < EMCMOT_MAX_AXIS; axis_num++) {
//orig:		    /* point to joint struct */
//orig:		    axis = &axes[axis_num];
//orig:		    /* tell teleop planner to stop */
//orig:		    axis->teleop_tp.enable = 0;
//orig:                }
	    } else if (GET_MOTION_COORD_FLAG()) {
		tpAbort(&emcmotDebug->coord_tp);
	    } else {
		for (joint_num = 0; joint_num < emcmotConfig->numJoints; joint_num++) {
		    /* point to joint struct */
		    joint = &joints[joint_num];
		    /* tell joint planner to stop */
		    joint->free_tp.enable = 0;
		    /* stop homing if in progress */
		    if ( joint->home_state != HOME_IDLE ) {
			joint->home_state = HOME_ABORT;
		    }
		}
	    }
            SET_MOTION_ERROR_FLAG(0);
	    /* clear joint errors (regardless of mode) */
	    for (joint_num = 0; joint_num < emcmotConfig->numJoints; joint_num++) {
		/* point to joint struct */
		joint = &joints[joint_num];
		/* update status flags */
		SET_JOINT_ERROR_FLAG(joint, 0);
		SET_JOINT_FAULT_FLAG(joint, 0);
	    }
	    emcmotStatus->paused = 0;
	    break;

	case EMCMOT_JOINT_ABORT:
	    /* abort one joint */
	    /* can happen at any time */
	    /* this command stops a single joint.  It is only usefull
	       in free mode, so in coord or teleop mode it does
	       nothing. */
	    rtapi_print_msg(RTAPI_MSG_DBG, "JOINT_ABORT");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    if (GET_MOTION_TELEOP_FLAG()) {
		axis = &axes[joint_num];
		/* tell teleop planner to stop */
		axis->teleop_tp.enable = 0;
		/* do nothing in teleop mode */
	    } else if (GET_MOTION_COORD_FLAG()) {
		/* do nothing in coord mode */
	    } else {
		/* validate joint */
		if (joint == 0) {
		    break;
		}
		/* tell joint planner to stop */
		joint->free_tp.enable = 0;
		/* stop homing if in progress */
		if ( joint->home_state != HOME_IDLE ) {
		    joint->home_state = HOME_ABORT;
		}
		/* update status flags */
		rtapi_print_msg(RTAPI_MSG_DBG, " SET_JOINT_ERROR_FLAG");
		SET_JOINT_ERROR_FLAG(joint, 0);
	    }
	    break;

	case EMCMOT_FREE:
	    /* change the mode to free mode motion (joint mode) */
	    /* can be done at any time */
	    /* this code doesn't actually make the transition, it merely
	       requests the transition by clearing a couple of flags */
	    /* reset the emcmotDebug->coordinating flag to defer transition
	       to controller cycle */
	    rtapi_print_msg(RTAPI_MSG_DBG, "FREE");
	    emcmotDebug->coordinating = 0;
	    emcmotDebug->teleoperating = 0;
	    break;

	case EMCMOT_COORD:
	    /* change the mode to coordinated axis motion */
	    /* can be done at any time */
	    /* this code doesn't actually make the transition, it merely
	       tests a condition and then sets a flag requesting the
	       transition */
	    /* set the emcmotDebug->coordinating flag to defer transition to
	       controller cycle */
	    rtapi_print_msg(RTAPI_MSG_DBG, "COORD");
	    emcmotDebug->coordinating = 1;
	    emcmotDebug->teleoperating = 0;
	    if (emcmotConfig->kinType != KINEMATICS_IDENTITY) {
		if (!checkAllHomed()) {
		    reportError
			(_("all joints must be homed before going into coordinated mode"));
		    emcmotDebug->coordinating = 0;
		    break;
		}
	    }
	    break;

	case EMCMOT_TELEOP:
	    /* change the mode to teleop motion */
	    /* can be done at any time */
	    /* this code doesn't actually make the transition, it merely
	       tests a condition and then sets a flag requesting the
	       transition */
	    /* set the emcmotDebug->teleoperating flag to defer transition to
	       controller cycle */
	    rtapi_print_msg(RTAPI_MSG_DBG, "TELEOP");
	    emcmotDebug->teleoperating = 1;
	    if (emcmotConfig->kinType != KINEMATICS_IDENTITY) {
		if (!checkAllHomed()) {
		    reportError(_("all joints must be homed before going into teleop mode"));
		    emcmotDebug->teleoperating = 0;
		    break;
		}
	    }
	    break;

	case EMCMOT_SET_NUM_JOINTS:
	    /* set the global NUM_JOINTS, which must be between 1 and
	       EMCMOT_MAX_JOINTS, inclusive */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_NUM_JOINTS");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", emcmotCommand->joint);
	    if (( emcmotCommand->joint <= 0 ) ||
		( emcmotCommand->joint > EMCMOT_MAX_JOINTS )) {
		break;
	    }
	    emcmotConfig->numJoints = emcmotCommand->joint;
	    break;

	case EMCMOT_SET_WORLD_HOME:
	    rtapi_print_msg(RTAPI_MSG_DBG, " SET_WORLD_HOME");
	    emcmotStatus->world_home = emcmotCommand->pos;
	    break;

	case EMCMOT_SET_JOINT_HOMING_PARAMS:
	    rtapi_print_msg(RTAPI_MSG_DBG, " SET_JOINT_HOMING_PARAMS");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    emcmot_config_change();
	    if (joint == 0) {
		break;
	    }
	    joint->home_offset = emcmotCommand->offset;
	    joint->home = emcmotCommand->home;
	    joint->home_final_vel = emcmotCommand->home_final_vel;
	    joint->home_search_vel = emcmotCommand->search_vel;
	    joint->home_latch_vel = emcmotCommand->latch_vel;
	    joint->home_flags = emcmotCommand->flags;
	    joint->home_sequence = emcmotCommand->home_sequence;
	    joint->volatile_home = emcmotCommand->volatile_home;
	    break;

	case EMCMOT_OVERRIDE_LIMITS:
	    /* this command can be issued with joint < 0 to re-enable
	       limits, but they are automatically re-enabled at the
	       end of the next jog */
	    rtapi_print_msg(RTAPI_MSG_DBG, " OVERRIDE_LIMITS");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    if (joint_num < 0) {
		/* don't override limits */
		rtapi_print_msg(RTAPI_MSG_DBG, "override off");
		emcmotStatus->overrideLimitMask = 0;
	    } else {
		rtapi_print_msg(RTAPI_MSG_DBG, "override on");
		emcmotStatus->overrideLimitMask = 0;
		for (joint_num = 0; joint_num < emcmotConfig->numJoints; joint_num++) {
		    /* point at joint data */
		    joint = &joints[joint_num];
		    /* only override limits that are currently tripped */
		    if ( GET_JOINT_NHL_FLAG(joint) ) {
			emcmotStatus->overrideLimitMask |= (1 << (joint_num*2));
		    }
		    if ( GET_JOINT_PHL_FLAG(joint) ) {
			emcmotStatus->overrideLimitMask |= (2 << (joint_num*2));
		    }
		}
	    }
	    emcmotDebug->overriding = 0;
	    for (joint_num = 0; joint_num < emcmotConfig->numJoints; joint_num++) {
		/* point at joint data */
		joint = &joints[joint_num];
		/* clear joint errors */
		SET_JOINT_ERROR_FLAG(joint, 0);
	    }
	    break;

	case EMCMOT_SET_JOINT_DISABLE_JOG:
	    rtapi_print_msg(RTAPI_MSG_DBG, " SET_JOINT_DISABLE_JOG");
	    rtapi_print_msg(RTAPI_MSG_DBG, " joint(%d): %d", joint_num, emcmotCommand->flags);
	    //orig: if(joint == 0) {
	    //orig:     break;
	    //orig: }
            assert(joint != 0);
	    joint->disable_jog = emcmotCommand->flags;
	    break;
	
        case EMCMOT_SET_JOINT_MOTOR_OFFSET:
	    rtapi_print_msg(RTAPI_MSG_DBG, " SET_JOINT_MOTOR_OFFSET");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    if(joint == 0) {
		break;
	    }
	    joint->motor_offset = emcmotCommand->motor_offset;
	    break;


	case EMCMOT_SET_JOINT_POSITION_LIMITS:
	    /* set the position limits for the joint */
	    /* can be done at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_JOINT_POSITION_LIMITS");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    emcmot_config_change();
	    if (joint == 0) {
		break;
	    }
	    joint->min_pos_limit = emcmotCommand->minLimit;
	    joint->max_pos_limit = emcmotCommand->maxLimit;
	    break;

	case EMCMOT_SET_JOINT_BACKLASH:
	    /* set the backlash for the joint */
	    /* can be done at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_JOINT_BACKLASH");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    emcmot_config_change();
	    if (joint == 0) {
		break;
	    }
	    joint->backlash = emcmotCommand->backlash;
	    break;

	    /*
	       Max and min ferror work like this: limiting ferror is
	       determined by slope of ferror line, = maxFerror/limitVel ->
	       limiting ferror = maxFerror/limitVel * vel. If ferror <
	       minFerror then OK else if ferror < limiting ferror then OK
	       else ERROR */
	case EMCMOT_SET_JOINT_MAX_FERROR:
	    rtapi_print_msg(RTAPI_MSG_DBG, " SET_JOINT_MAX_FERROR");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    emcmot_config_change();
	    if (joint == 0 || emcmotCommand->maxFerror < 0.0) {
		break;
	    }
	    joint->max_ferror = emcmotCommand->maxFerror;
	    break;

	case EMCMOT_SET_JOINT_MIN_FERROR:
	    rtapi_print_msg(RTAPI_MSG_DBG, " SET_JOINT_MIN_FERROR");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    emcmot_config_change();
	    if (joint == 0 || emcmotCommand->minFerror < 0.0) {
		break;
	    }
	    joint->min_ferror = emcmotCommand->minFerror;
	    break;

	case EMCMOT_JOG_CONT:

	    /* do a continuous jog, implemented as an incremental jog to the
	       limit.  When the user lets go of the button an abort will
	       stop the jog. */
	    rtapi_print_msg(RTAPI_MSG_DBG, " JOG_CONT");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    if (joint == 0) {
		break;
	    }
	    /* must be in free mode and enabled */
	    if (GET_MOTION_COORD_FLAG()) {
		reportError(_("Can't jog joint in coordinated mode."));
		SET_JOINT_ERROR_FLAG(joint, 1);
		break;
	    }
	    if (!GET_MOTION_ENABLE_FLAG()) {
		reportError(_("Can't jog joint when not enabled."));
		SET_JOINT_ERROR_FLAG(joint, 1);
		break;
	    }
	    if (emcmotStatus->homing_active) {
		reportError(_("Can't jog any joints while homing."));
		SET_JOINT_ERROR_FLAG(joint, 1);
		break;
	    }
	    if (emcmotStatus->net_feed_scale < 0.0001) {
		/* don't jog if feedhold is on or if feed override is zero */
		break;
	    }
            if (!GET_MOTION_TELEOP_FLAG()) {
	        if (joint->wheel_jog_active) {
		    /* can't do two kinds of jog at once */
		    break;
	        }
                if (joint->home_flags & HOME_UNLOCK_FIRST) {
                    reportError("Can't jog a locking joint.");
                    SET_JOINT_ERROR_FLAG(joint, 1);
                    break;
                }
	        /* don't jog further onto limits */
	        if (!jog_ok(joint_num, emcmotCommand->vel)) {
		    SET_JOINT_ERROR_FLAG(joint, 1);
		    break;
	        }
	        /* set destination of jog */
	        refresh_jog_limits(joint);
	        if (emcmotCommand->vel > 0.0) {
		    joint->free_tp.pos_cmd = joint->max_jog_limit;
	        } else {
		    joint->free_tp.pos_cmd = joint->min_jog_limit;
	        }
	        /* set velocity of jog */
	        joint->free_tp.max_vel = fabs(emcmotCommand->vel);
	        /* use max joint accel */
	        joint->free_tp.max_acc = joint->acc_limit;
	        /* lock out other jog sources */
	        joint->kb_jog_active = 1;
	        /* and let it go */
	        joint->free_tp.enable = 1;
                joint->free_tp.position_mode = 0; // jerk limition without accurate positioning

	        /*! \todo FIXME - should we really be clearing errors here? */
	        SET_JOINT_ERROR_FLAG(joint, 0);
	        /* clear joints homed flag(s) if we don't have forward kins.
	           Otherwise, a transition into coordinated mode will incorrectly
	           assume the homed position. Do all if they've all been moved
	           since homing, otherwise just do this one */
	        clearHomes(joint_num);
            } else {
                axis_num = emcmotCommand->joint;
                if (axis_num >= 0 && axis_num < EMCMOT_MAX_AXIS) {
                    /* valid axis, point to it's data */
                    axis = &axes[axis_num];
                }

	        if (emcmotCommand->vel > 0.0) {//TODO-eric: call kin API for max or min value
		    axis->teleop_tp.pos_cmd = axis->max_pos_limit;
	        } else {
		    axis->teleop_tp.pos_cmd = axis->min_pos_limit;
	        }

                /* set velocity of jog */
	        axis->teleop_tp.max_vel = fabs(emcmotCommand->vel);
	        /* use max axis accel */
	        axis->teleop_tp.max_acc = axis->acc_limit;
	        /* and let it go */
	        axis->teleop_tp.enable = 1;
            }
	    break;

	case EMCMOT_JOG_INCR:
	    /* do an incremental jog */
	    rtapi_print_msg(RTAPI_MSG_DBG, "JOG_INCR");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    if (joint == 0) {
		break;
	    }
	    /* must be in free mode and enabled */
	    if (GET_MOTION_COORD_FLAG()) {
		reportError(_("Can't jog joint in coordinated mode."));
		SET_JOINT_ERROR_FLAG(joint, 1);
		break;
	    }
	    if (!GET_MOTION_ENABLE_FLAG()) {
		reportError(_("Can't jog joint when not enabled."));
		SET_JOINT_ERROR_FLAG(joint, 1);
		break;
	    }
	    if (emcmotStatus->homing_active) {
		reportError(_("Can't jog any joint while homing."));
		SET_JOINT_ERROR_FLAG(joint, 1);
		break;
	    }
	    if (emcmotStatus->net_feed_scale < 0.0001 ) {
		/* don't jog if feedhold is on or if feed override is zero */
		break;
	    }
            if (!GET_MOTION_TELEOP_FLAG()) {
	        if (joint->wheel_jog_active) {
		    /* can't do two kinds of jog at once */
		    break;
	        }
                if (joint->home_flags & HOME_UNLOCK_FIRST) {
                    reportError("Can't jog a locking joint.");
                    SET_JOINT_ERROR_FLAG(joint, 1);
                    break;
                }
	        /* don't jog further onto limits */
	        if (!jog_ok(joint_num, emcmotCommand->vel)) {
		    SET_JOINT_ERROR_FLAG(joint, 1);
		    break;
	        }
	        /* set target position for jog */
	        if (emcmotCommand->vel > 0.0) {
		    tmp1 = joint->free_tp.pos_cmd + emcmotCommand->offset;
	        } else {
		    tmp1 = joint->free_tp.pos_cmd - emcmotCommand->offset;
	        }
	        /* don't jog past limits */
	        refresh_jog_limits(joint);
	        if (tmp1 > joint->max_jog_limit) {
		    break;
	        }
	        if (tmp1 < joint->min_jog_limit) {
		    break;
	        }
	        /* set target position */
	        joint->free_tp.pos_cmd = tmp1;
	        /* set velocity of jog */
	        joint->free_tp.max_vel = fabs(emcmotCommand->vel);
	        /* use max joint accel */
	        joint->free_tp.max_acc = joint->acc_limit;
	        /* lock out other jog sources */
	        joint->kb_jog_active = 1;
	        /* and let it go */
	        joint->free_tp.enable = 1;
                joint->free_tp.position_mode = 1; // accurate position for jog-incremental
	        SET_JOINT_ERROR_FLAG(joint, 0);
	        /* clear joint homed flag(s) if we don't have forward kins.
	           Otherwise, a transition into coordinated mode will incorrectly
	           assume the homed position. Do all if they've all been moved
	           since homing, otherwise just do this one */
	        clearHomes(joint_num);
            } else {
                axis_num = emcmotCommand->joint;
                if (axis_num >= 0 && axis_num < EMCMOT_MAX_AXIS) {
                    /* valid axis, point to it's data */
                    axis = &axes[axis_num];
                }
	        if (emcmotCommand->vel > 0.0) {
		    tmp1 = axis->teleop_tp.pos_cmd + emcmotCommand->offset;
	        } else {
		    tmp1 = axis->teleop_tp.pos_cmd - emcmotCommand->offset;
	        }
	        /* don't jog past limits */
	        if (tmp1 > axis->max_pos_limit) {
		    break;
	        }
	        if (tmp1 < axis->min_pos_limit) {
		    break;
	        }
	        /* set target position */
	        axis->teleop_tp.pos_cmd = tmp1;
                /* set velocity of jog */
	        axis->teleop_tp.max_vel = fabs(emcmotCommand->vel);
	        /* use max axis accel */
	        axis->teleop_tp.max_acc = axis->acc_limit;
	        /* and let it go */
	        axis->teleop_tp.enable = 1;
            }
	    break;

	case EMCMOT_JOG_ABS:
	    /* do an absolute jog */
	    rtapi_print_msg(RTAPI_MSG_DBG, "JOG_ABS");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    if (joint == 0) {
		break;
	    }
	    /* must be in free mode and enabled */
	    if (GET_MOTION_COORD_FLAG()) {
		reportError(_("Can't jog joint in coordinated mode."));
		SET_JOINT_ERROR_FLAG(joint, 1);
		break;
	    }
	    if (!GET_MOTION_ENABLE_FLAG()) {
		reportError(_("Can't jog joint when not enabled."));
		SET_JOINT_ERROR_FLAG(joint, 1);
		break;
	    }
	    if (emcmotStatus->homing_active) {
		reportError(_("Can't jog any joints while homing."));
		SET_JOINT_ERROR_FLAG(joint, 1);
		break;
	    }
	    if (joint->wheel_jog_active) {
		/* can't do two kinds of jog at once */
		break;
	    }
	    if (emcmotStatus->net_feed_scale < 0.0001 ) {
		/* don't jog if feedhold is on or if feed override is zero */
		break;
	    }
	    /* don't jog further onto limits */
	    if (!jog_ok(joint_num, emcmotCommand->vel)) {
		SET_JOINT_ERROR_FLAG(joint, 1);
		break;
	    }
	    /*! \todo FIXME-- use 'goal' instead */
	    joint->free_tp.pos_cmd = emcmotCommand->offset;
	    /* don't jog past limits */
	    refresh_jog_limits(joint);
	    if (joint->free_tp.pos_cmd > joint->max_jog_limit) {
		joint->free_tp.pos_cmd = joint->max_jog_limit;
	    }
	    if (joint->free_tp.pos_cmd < joint->min_jog_limit) {
		joint->free_tp.pos_cmd = joint->min_jog_limit;
	    }
	    /* set velocity of jog */
	    joint->free_tp.max_vel = fabs(emcmotCommand->vel);
	    /* use max joint accel */
	    joint->free_tp.max_acc = joint->acc_limit;
	    /* lock out other jog sources */
	    joint->kb_jog_active = 1;
	    /* and let it go */
	    joint->free_tp.enable = 1;
            joint->free_tp.position_mode = 0; // absolute jog: jerk limition without accurate positioning
	    SET_JOINT_ERROR_FLAG(joint, 0);
	    /* clear joint homed flag(s) if we don't have forward kins.
	       Otherwise, a transition into coordinated mode will incorrectly
	       assume the homed position. Do all if they've all been moved
	       since homing, otherwise just do this one */
	    clearHomes(joint_num);
	    break;

	case EMCMOT_SET_TERM_COND:
	    /* sets termination condition for motion emcmotDebug->coord_tp */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_TERM_COND");
	    tpSetTermCond(&emcmotDebug->coord_tp, emcmotCommand->termCond, emcmotCommand->tolerance);
	    break;

        case EMCMOT_SET_SPINDLESYNC:
            tpSetSpindleSync(&emcmotDebug->coord_tp, emcmotCommand->spindlesync, emcmotCommand->flags);
            break;

        case EMCMOT_SET_NURBS:
            //TODO: have to consider several condition
            tpAddNURBS(&emcmotDebug->coord_tp, emcmotCommand->motion_type,
                       emcmotCommand->nurbs_block, emcmotCommand->pos,
                       emcmotStatus->enables_new, emcmotCommand->vel,
                       emcmotCommand->ini_maxvel,
                       emcmotCommand->ini_maxacc,
                       emcmotCommand->ini_maxjerk);
            break;
	case EMCMOT_SET_LINE:
	    /* emcmotDebug->coord_tp up a linear move */
	    /* requires motion enabled, coordinated mode, not on limits */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_LINE");
	    if (!GET_MOTION_COORD_FLAG() || !GET_MOTION_ENABLE_FLAG()) {
		reportError(_("need to be enabled, in coord mode for linear move"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_COMMAND;
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else if (!inRange(emcmotCommand->pos, emcmotCommand->id, "Linear")) {
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_PARAMS;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else if (!limits_ok()) {
		reportError(_("can't do linear move with limits exceeded"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_PARAMS;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    }
            if(emcmotStatus->atspeed_next_feed && is_feed_type(emcmotCommand->motion_type) ) {
                issue_atspeed = 1;
                emcmotStatus->atspeed_next_feed = 0;
            }
            if(!is_feed_type(emcmotCommand->motion_type) && emcmotStatus->spindle.css_factor) {
                emcmotStatus->atspeed_next_feed = 1;
            }
	    /* append it to the emcmotDebug->coord_tp */
	    tpSetId(&emcmotDebug->coord_tp, emcmotCommand->id);
	    if (-1 == tpAddLine(&emcmotDebug->coord_tp, emcmotCommand->pos, emcmotCommand->motion_type, 
                                emcmotCommand->vel, emcmotCommand->ini_maxvel, 
                                emcmotCommand->acc, emcmotCommand->ini_maxjerk, emcmotStatus->enables_new, issue_atspeed,
                                emcmotCommand->turn)) {
		reportError(_("can't add linear move"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_BAD_EXEC;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else {
		SET_MOTION_ERROR_FLAG(0);
		/* set flag that indicates all joints need rehoming, if any
		   joint is moved in joint mode, for machines with no forward
		   kins */
		rehomeAll = 1;
	    }
	    break;

	case EMCMOT_SET_CIRCLE:
	    /* emcmotDebug->coord_tp up a circular move */
	    /* requires coordinated mode, enable on, not on limits */
	    rtapi_print_msg(RTAPI_MSG_DBG, " SET_CIRCLE");
	    if (!GET_MOTION_COORD_FLAG() || !GET_MOTION_ENABLE_FLAG()) {
		reportError(_("need to be enabled, in coord mode for circular move"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_COMMAND;
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else if (!inRange(emcmotCommand->pos, emcmotCommand->id, "Circular")) {
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_PARAMS;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else if (!limits_ok()) {
		reportError(_("can't do circular move with limits exceeded"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_PARAMS;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    }
            if(emcmotStatus->atspeed_next_feed) {
                issue_atspeed = 1;
                emcmotStatus->atspeed_next_feed = 0;
            }
	    /* append it to the emcmotDebug->coord_tp */
	    tpSetId(&emcmotDebug->coord_tp, emcmotCommand->id);
	    if (-1 ==
		tpAddCircle(&emcmotDebug->coord_tp, emcmotCommand->pos,
                            emcmotCommand->center, emcmotCommand->normal,
                            emcmotCommand->turn, emcmotCommand->motion_type,
                            emcmotCommand->vel, emcmotCommand->ini_maxvel,
                            emcmotCommand->acc, emcmotCommand->ini_maxjerk,
                            emcmotStatus->enables_new, issue_atspeed)) {
		reportError(_("can't add circular move"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_BAD_EXEC;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else {
		SET_MOTION_ERROR_FLAG(0);
		/* set flag that indicates all joints need rehoming, if any
		   joint is moved in joint mode, for machines with no forward
		   kins */
		rehomeAll = 1;
	    }
	    break;

	case EMCMOT_SET_VEL:
	    /* set the velocity for subsequent moves */
	    /* can do it at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, " SET_VEL");
	    emcmotStatus->vel = emcmotCommand->vel;
	    tpSetVmax(&emcmotDebug->coord_tp, emcmotStatus->vel, emcmotCommand->ini_maxvel);
	    break;

	case EMCMOT_SET_VEL_LIMIT:
	    rtapi_print_msg(RTAPI_MSG_DBG, " SET_VEL_LIMIT");
	    emcmot_config_change();
	    /* set the absolute max velocity for all subsequent moves */
	    /* can do it at any time */
	    emcmotConfig->limitVel = emcmotCommand->vel;
	    tpSetVlimit(&emcmotDebug->coord_tp, emcmotConfig->limitVel);
	    break;

	case EMCMOT_SET_JOINT_VEL_LIMIT:
	    /* set joint max velocity */
	    /* can do it at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_JOINT_VEL_LIMIT");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    emcmot_config_change();
	    /* check joint range */
	    if (joint == 0) {
		break;
	    }
	    joint->vel_limit = emcmotCommand->vel;
	    break;

	case EMCMOT_SET_JOINT_ACC_LIMIT:
	    /* set joint max acceleration */
	    /* can do it at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_JOINT_ACC_LIMIT");
	    rtapi_print_msg(RTAPI_MSG_DBG, " j(%d) acc(%f)", joint_num, emcmotCommand->acc);
	    emcmot_config_change();
	    //obsolete: /* check joint range */
	    //obsolete: if (joint == 0) {
	    //obsolete:        break;
	    //obsolete: }
	    assert (joint != 0); // the joint pointer must not be NULL
	    joint->acc_limit = emcmotCommand->acc;
	    break;

	case EMCMOT_SET_JOINT_JERK_LIMIT:
	    /* set joint max jerk */
	    /* can do it at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_JOINT_JERK_LIMIT");
	    rtapi_print_msg(RTAPI_MSG_DBG, " j(%d) jerk(%f)", joint_num, emcmotCommand->jerk);
	    emcmot_config_change();
	    //obsolete: /* check joint range */
	    //obsolete: if (joint == 0) {
	    //obsolete:        break;
	    //obsolete: }
	    assert (joint != 0); // the joint pointer must not be NULL
	    joint->jerk_limit = emcmotCommand->jerk;
	    break;

	case EMCMOT_SET_ACC:
	    /* set the traj acceleration for jogging */
	    /* can do it at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_ACC, acc(%f)", emcmotCommand->acc);
	    emcmotStatus->acc = emcmotCommand->acc;
	    //obsolete: tpSetAmax(&emcmotDebug->coord_tp, emcmotStatus->acc);
	    break;

	case EMCMOT_SET_JERK:
	    /* set the traj jerk for jogging */
	    /* can do it at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_JERK, jerk(%f)", emcmotCommand->jerk);
	    emcmotStatus->jerk = emcmotCommand->jerk;
	    break;

	case EMCMOT_PAUSE:
	    /* pause the motion */
	    /* can happen at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "PAUSE");
	    tpPause(&emcmotDebug->coord_tp);
	    emcmotStatus->paused = 1;
	    break;

	case EMCMOT_RESUME:
	    /* resume paused motion */
	    /* can happen at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, " RESUME");
	    emcmotDebug->stepping = 0;
	    tpResume(&emcmotDebug->coord_tp);
	    emcmotStatus->paused = 0;
	    break;

	case EMCMOT_STEP:
	    /* resume paused motion until id changes */
	    /* can happen at any time */
            rtapi_print_msg(RTAPI_MSG_DBG, " STEP");
            if(emcmotStatus->paused) {
                emcmotDebug->idForStep = emcmotStatus->id;
                emcmotDebug->stepping = 1;
                tpResume(&emcmotDebug->coord_tp);
                emcmotStatus->paused = 1;
            } else {
		reportError(_("MOTION: can't STEP while already executing"));
	    }
	    break;

	case EMCMOT_FEED_SCALE:
	    /* override speed */
	    /* can happen at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, " FEED_SCALE");
	    if (emcmotCommand->scale < 0.0) {
		emcmotCommand->scale = 0.0;	/* clamp it */
	    }
	    emcmotStatus->feed_scale = emcmotCommand->scale;
	    break;

	case EMCMOT_FS_ENABLE:
	    /* enable/disable overriding speed */
	    /* can happen at any time */
	    if ( emcmotCommand->mode != 0 ) {
		rtapi_print_msg(RTAPI_MSG_DBG, " FS_ENABLE: ON");
		emcmotStatus->enables_new |= FS_ENABLED;
            } else {
		rtapi_print_msg(RTAPI_MSG_DBG, " FS_ENABLE: OFF");
		emcmotStatus->enables_new &= ~FS_ENABLED;
	    }
	    break;

	case EMCMOT_FH_ENABLE:
	    /* enable/disable feed hold */
	    /* can happen at any time */
	    if ( emcmotCommand->mode != 0 ) {
		rtapi_print_msg(RTAPI_MSG_DBG, " FH_ENABLE: ENABLED");
		emcmotStatus->enables_new |= FH_ENABLED;
            } else {
		rtapi_print_msg(RTAPI_MSG_DBG, " FH_ENABLE: DISABLED");
		emcmotStatus->enables_new &= ~FH_ENABLED;
	    }
	    break;

	case EMCMOT_SPINDLE_SCALE:
	    /* override spindle speed */
	    /* can happen at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, " SPINDLE_SCALE");
	    if (emcmotCommand->scale < 0.0) {
		emcmotCommand->scale = 0.0;	/* clamp it */
	    }
	    emcmotStatus->spindle_scale = emcmotCommand->scale;
	    break;

	case EMCMOT_SS_ENABLE:
	    /* enable/disable overriding spindle speed */
	    /* can happen at any time */
	    if ( emcmotCommand->mode != 0 ) {
		rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE SCALE: ON");
		emcmotStatus->enables_new |= SS_ENABLED;
            } else {
		rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE SCALE: OFF");
		emcmotStatus->enables_new &= ~SS_ENABLED;
	    }
	    break;

	case EMCMOT_AF_ENABLE:
	    /* enable/disable adaptive feedrate override from HAL pin */
	    /* can happen at any time */
	    if ( emcmotCommand->flags != 0 ) {
		rtapi_print_msg(RTAPI_MSG_DBG, "ADAPTIVE FEED: ON");
		emcmotStatus->enables_new |= AF_ENABLED;
            } else {
		rtapi_print_msg(RTAPI_MSG_DBG, "ADAPTIVE FEED: OFF");
		emcmotStatus->enables_new &= ~AF_ENABLED;
	    }
	    break;

	case EMCMOT_DISABLE:
	    /* go into disable */
	    /* can happen at any time */
	    /* reset the emcmotDebug->enabling flag to defer disable until
	       controller cycle (it *will* be honored) */
	    rtapi_print_msg(RTAPI_MSG_DBG, "DISABLE");
	    emcmotDebug->enabling = 0;
	    if (emcmotConfig->kinType == KINEMATICS_INVERSE_ONLY) {
		emcmotDebug->teleoperating = 0;
		emcmotDebug->coordinating = 0;
	    }
	    break;

	case EMCMOT_ENABLE:
	    /* come out of disable */
	    /* can happen at any time */
	    /* set the emcmotDebug->enabling flag to defer enable until
	       controller cycle */
	    rtapi_print_msg(RTAPI_MSG_DBG, "ENABLE");
	    if ( *(emcmot_hal_data->enable) == 0 ) {
		reportError(_("can't enable motion, enable input is false"));
	    } else {
		emcmotDebug->enabling = 1;
		if (emcmotConfig->kinType == KINEMATICS_INVERSE_ONLY) {
		    emcmotDebug->teleoperating = 0;
		    emcmotDebug->coordinating = 0;
		}
	    }
	    break;

	case EMCMOT_JOINT_ACTIVATE:
	    /* make joint active, so that amps will be enabled when system is
	       enabled or disabled */
	    /* can be done at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "JOINT_ACTIVATE");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    if (joint == 0) {
		break;
	    }
	    SET_JOINT_ACTIVE_FLAG(joint, 1);
	    break;

	case EMCMOT_JOINT_DEACTIVATE:
	    /* make joint inactive, so that amps won't be affected when system
	       is enabled or disabled */
	    /* can be done at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "JOINT_DEACTIVATE");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    if (joint == 0) {
		break;
	    }
	    SET_JOINT_ACTIVE_FLAG(joint, 0);
	    break;
/*! \todo FIXME - need to replace the ext function */
	case EMCMOT_JOINT_ENABLE_AMPLIFIER:
	    /* enable the amplifier directly, but don't enable calculations */
	    /* can be done at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "JOINT_ENABLE_AMP");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    if (joint == 0) {
		break;
	    }
/*! \todo Another #if 0 */
#if 0
	    extAmpEnable(joint_num, 1);
#endif
	    break;

	case EMCMOT_JOINT_DISABLE_AMPLIFIER:
	    /* disable the joint calculations and amplifier, but don't disable
	       calculations */
	    /* can be done at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "JOINT_DISABLE_AMP");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
	    if (joint == 0) {
		break;
	    }
/*! \todo Another #if 0 */
#if 0
	    extAmpEnable(joint_num, 0);
#endif
	    break;

	case EMCMOT_JOINT_HOME:
	    /* home the specified joint */
	    /* need to be in free mode, enable on */
	    /* this just sets the initial state, then the state machine in
	       homing.c does the rest */
	    rtapi_print_msg(RTAPI_MSG_DBG, "JOINT_HOME");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);

	    if (emcmotStatus->motion_state != EMCMOT_MOTION_FREE) {
		/* can't home unless in free mode */
		reportError(_("must be in joint mode to home"));
		return;
	    }
	    if (!GET_MOTION_ENABLE_FLAG()) {
		break;
	    }

	    if(joint_num == -1) {
                if(emcmotStatus->homingSequenceState == HOME_SEQUENCE_IDLE)
                    emcmotStatus->homingSequenceState = HOME_SEQUENCE_START;
                else
                    reportError(_("homing sequence already in progress"));
		break;
	    }

	    if (joint == NULL) {
		break;
	    }

            if(joint->home_state != HOME_IDLE) {
                reportError(_("homing already in progress"));
            } else if(emcmotStatus->homingSequenceState != HOME_SEQUENCE_IDLE) {
                reportError(_("homing sequence already in progress"));
            } else {
                /* abort any movement (jog, etc) that is in progress */
                joint->free_tp.enable = 0;
                
                /* prime the homing state machine */
                joint->home_state = HOME_START;
            }
	    break;

	case EMCMOT_JOINT_UNHOME:
            /* unhome the specified joint, or all joints if -1 */
            rtapi_print_msg(RTAPI_MSG_DBG, "JOINT_UNHOME");
            rtapi_print_msg(RTAPI_MSG_DBG, " %d", joint_num);
            
            if ((emcmotStatus->motion_state != EMCMOT_MOTION_FREE) && (emcmotStatus->motion_state != EMCMOT_MOTION_DISABLED)) {
                reportError(_("must be in joint mode or disabled to unhome"));
                return;
            }

            if (joint_num < 0) {
                /* we want all or none, so these checks need to all be done first.
                 * but, let's only report the first error.  There might be several,
                 * for instance if a homing sequence is running. */
                for (n = 0; n < emcmotConfig->numJoints; n++) {
                    joint = &joints[n];
                    if(GET_JOINT_ACTIVE_FLAG(joint)) {
                        if (GET_JOINT_HOMING_FLAG(joint)) {
                            reportError(_("Cannot unhome while homing, joint %d"), n);
                            return;
                        }
                        if (!GET_JOINT_INPOS_FLAG(joint)) {
                            reportError(_("Cannot unhome while moving, joint %d"), n);
                            return;
                        }
                    }
                }
                /* we made it through the checks, so unhome them all */
                for (n = 0; n < emcmotConfig->numJoints; n++) {
                    joint = &joints[n];
                    if(GET_JOINT_ACTIVE_FLAG(joint)) {
                        /* if -2, only unhome the volatile_home joints */
                        if(joint_num != -2 || joint->volatile_home) {
                            SET_JOINT_HOMED_FLAG(joint, 0);
                        }
                    }
                }
            } else if (joint_num < emcmotConfig->numJoints) {
                /* request was for only one joint */
                if(GET_JOINT_ACTIVE_FLAG(joint)) {
                    if (GET_JOINT_HOMING_FLAG(joint)) {
                        reportError(_("Cannot unhome while homing, joint %d"), joint_num);
                        return;
                    }
                    if (!GET_JOINT_INPOS_FLAG(joint)) {
                        reportError(_("Cannot unhome while moving, joint %d"), joint_num);
                        return;
                    }
                    SET_JOINT_HOMED_FLAG(joint, 0);
                } else {
                    reportError(_("Cannot unhome inactive joint %d"), joint_num);
                }
            } else {
                /* invalid joint number specified */
                reportError(_("Cannot unhome invalid joint %d (max %d)"), joint_num, (emcmotConfig->numJoints-1));
                return;
            }

            break;

	case EMCMOT_CLEAR_PROBE_FLAGS:
//	    rtapi_print_msg(RTAPI_MSG_DBG, "CLEAR_PROBE_FLAGS");
//	    if (emcmotStatus->probe_cmd != USB_CMD_NOOP) {
//	        reportError(_("initiate probe command while usb_cmd is not USB_CMD_NOOP"));
//	        fprintf(stderr,"initiate probe command while usb_cmd is not USB_CMD_NOOP");
//	    }
	    break;

	case EMCMOT_PROBE:
	    /* most of this is taken from EMCMOT_SET_LINE */
	    /* emcmotDebug->coord_tp up a linear move */
	    /* requires coordinated mode, enable off, not on limits */
	    rtapi_print_msg(RTAPI_MSG_DBG, "PROBE");
	    if (!GET_MOTION_COORD_FLAG() || !GET_MOTION_ENABLE_FLAG()) {
		reportError(_("need to be enabled, in coord mode for probe move"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_COMMAND;
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else if (!inRange(emcmotCommand->pos, emcmotCommand->id, "Probe")) {
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_PARAMS;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else if (!limits_ok()) {
		reportError(_("can't do probe move with limits exceeded"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_PARAMS;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } /* else if (!(emcmotCommand->probe_type & 1)) {
                // if suppress errors = off...

                int probeval = !!*(emcmot_hal_data->probe_input);
                int probe_whenclears = !!(emcmotCommand->probe_type & 2);

                if (probeval != probe_whenclears) {
                    // the probe is already in the state we're seeking.
                    if(probe_whenclears) 
                        reportError(_("Probe is already clear when starting G38.4 or G38.5 move"));
                    else
                        reportError(_("Probe is already tripped when starting G38.2 or G38.3 move"));

                    emcmotStatus->commandStatus = EMCMOT_COMMAND_BAD_EXEC;
                    tpAbort(&emcmotDebug->coord_tp);
                    SET_MOTION_ERROR_FLAG(1);
                    break;
                }
            } */

	    /* append it to the emcmotDebug->coord_tp */
	    tpSetId(&emcmotDebug->coord_tp, emcmotCommand->id);
            if (-1 == tpAddLine(&emcmotDebug->coord_tp, emcmotCommand->pos,
                                emcmotCommand->motion_type, emcmotCommand->vel,
                                emcmotCommand->ini_maxvel,
                                emcmotCommand->acc,
                                emcmotCommand->ini_maxjerk,
                                emcmotStatus->enables_new, 0, -1)) {
		reportError(_("can't add probe move"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_BAD_EXEC;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else {
//		emcmotStatus->probing = 1;
                emcmotStatus->probe_type = emcmotCommand->probe_type;
		SET_MOTION_ERROR_FLAG(0);
		/* set flag that indicates all joints need rehoming, if any
		   joint is moved in joint mode, for machines with no forward
		   kins */
		rehomeAll = 1;

                if (emcmotCommand->probe_type & 2) {
                  // G38.2, G38.3  
                  emcmotStatus->probe_cmd = USB_CMD_PROBE_HIGH;
                  emcmotStatus->usb_cmd |= PROBE_CMD_TYPE;
                  emcmotStatus->usb_cmd_param[0] = (double) USB_CMD_PROBE_HIGH;
                } else {
                  // G38.4, G38.5  
                  emcmotStatus->probe_cmd = USB_CMD_PROBE_LOW;
                  emcmotStatus->usb_cmd |= PROBE_CMD_TYPE;
                  emcmotStatus->usb_cmd_param[0] = (double) USB_CMD_PROBE_LOW;
                }
                fprintf(stderr,"usb_cmd(0x%0x) usb_cmd_param(%f)\n",
                    emcmotStatus->usb_cmd, emcmotStatus->usb_cmd_param[0]);
	    }
	    break;

	case EMCMOT_RIGID_TAP:
	    /* most of this is taken from EMCMOT_SET_LINE */
	    /* emcmotDebug->coord_tp up a linear move */
	    /* requires coordinated mode, enable off, not on limits */
	    rtapi_print_msg(RTAPI_MSG_DBG, "RIGID_TAP");
	    if (!GET_MOTION_COORD_FLAG() || !GET_MOTION_ENABLE_FLAG()) {
		reportError(_("need to be enabled, in coord mode for rigid tap move"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_COMMAND;
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else if (!inRange(emcmotCommand->pos, emcmotCommand->id, "Rigid tap")) {
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_PARAMS;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else if (!limits_ok()) {
		reportError(_("can't do rigid tap move with limits exceeded"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_PARAMS;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    }

	    /* append it to the emcmotDebug->coord_tp */
	    tpSetId(&emcmotDebug->coord_tp, emcmotCommand->id);
            if (-1 == tpAddRigidTap(&emcmotDebug->coord_tp, 
                                    emcmotCommand->pos, emcmotCommand->vel,
                                    emcmotCommand->ini_maxvel,
                                    emcmotCommand->acc,
                                    emcmotCommand->ini_maxjerk,
                                    emcmotStatus->enables_new)) {
                emcmotStatus->atspeed_next_feed = 0; /* rigid tap always waits for spindle to be at-speed */
		reportError(_("can't add rigid tap move"));
		emcmotStatus->commandStatus = EMCMOT_COMMAND_BAD_EXEC;
		tpAbort(&emcmotDebug->coord_tp);
		SET_MOTION_ERROR_FLAG(1);
		break;
	    } else {
		SET_MOTION_ERROR_FLAG(0);
	    }
	    break;

	case EMCMOT_SET_TELEOP_VECTOR:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_TELEOP_VECTOR");
	    if (!GET_MOTION_TELEOP_FLAG() || !GET_MOTION_ENABLE_FLAG()) {
		reportError
		    (_("need to be enabled, in teleop mode for teleop move"));
	    } else {
		double velmag;
		emcmotDebug->teleop_data.desiredVel = emcmotCommand->pos;
		pmCartMag(emcmotDebug->teleop_data.desiredVel.tran, &velmag);
		if (emcmotDebug->teleop_data.desiredVel.a > velmag) {
		    velmag = emcmotDebug->teleop_data.desiredVel.a;
		}
		if (emcmotDebug->teleop_data.desiredVel.b > velmag) {
		    velmag = emcmotDebug->teleop_data.desiredVel.b;
		}
		if (emcmotDebug->teleop_data.desiredVel.c > velmag) {
		    velmag = emcmotDebug->teleop_data.desiredVel.c;
		}
		if (velmag > emcmotConfig->limitVel) {
		    pmCartScalMult(emcmotDebug->teleop_data.desiredVel.tran,
			emcmotConfig->limitVel / velmag,
			&emcmotDebug->teleop_data.desiredVel.tran);
		    emcmotDebug->teleop_data.desiredVel.a *=
			emcmotConfig->limitVel / velmag;
		    emcmotDebug->teleop_data.desiredVel.b *=
			emcmotConfig->limitVel / velmag;
		    emcmotDebug->teleop_data.desiredVel.c *=
			emcmotConfig->limitVel / velmag;
		}
		/**
		 * 2012-09-21 ysli TODO:
		 * We should limit the desiredVel vector based on each AXES's MAX_VEL.
		 * Not simply the [TRAJ]MAX_LINEAR_VELOCITY
		 **/
		/* flag that all joints need to be homed, if any joint is
		   jogged individually later */
		rehomeAll = 1;
	    }
	    break;

	case EMCMOT_SET_DEBUG:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_DEBUG");
	    emcmotConfig->debug = emcmotCommand->debug;
	    emcmot_config_change();
	    break;

	/* needed for synchronous I/O */
	case EMCMOT_SET_AOUT:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_AOUT");
	    if (emcmotCommand->now) { //we set it right away
		emcmotAioWrite(emcmotCommand->out, emcmotCommand->minLimit);
	    } else { // we put it on the TP queue, warning: only room for one in there, any new ones will overwrite
		tpSetAout(&emcmotDebug->coord_tp, emcmotCommand->out,
		    emcmotCommand->minLimit, emcmotCommand->maxLimit);
	    }
	    break;

	case EMCMOT_SET_DOUT:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_DOUT");
	    if (emcmotCommand->now) { //we set it right away
		emcmotDioWrite(emcmotCommand->out, emcmotCommand->start);
	    } else { // we put it on the TP queue, warning: only room for one in there, any new ones will overwrite
		tpSetDout(&emcmotDebug->coord_tp, emcmotCommand->out,
		    emcmotCommand->start, emcmotCommand->end);
	    }
	    break;
	case EMCMOT_SET_SYNC_INPUT:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_DOUT");
            if (emcmotCommand->now) { //we set it right away
                emcmotSyncInputWrite(emcmotCommand->out,emcmotCommand->timeout,
                        emcmotCommand->wait_type);
            } else { // we put it on the TP queue, warning: only room for one in there, any new ones will overwrite
                tpSetSyncInput(&emcmotDebug->coord_tp, emcmotCommand->out,
                    emcmotCommand->timeout, emcmotCommand->wait_type);
            }
	    break;
	case EMCMOT_SPINDLE_ON:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE_ON");

	    if (*(emcmot_hal_data->spindle_orient)) 
		rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE_ORIENT cancelled by SPINDLE_ON");
	    if (*(emcmot_hal_data->spindle_locked))
		rtapi_print_msg(RTAPI_MSG_DBG, "spindle-locked cleared by SPINDLE_ON");
	    *(emcmot_hal_data->spindle_locked) = 0;
	    *(emcmot_hal_data->spindle_orient) = 0;
	    emcmotStatus->spindle.orient_state = EMCMOT_ORIENT_NONE;

	    /* if (emcmotStatus->spindle.orient) { */
	    /* 	reportError(_("cant turn on spindle during orient in progress")); */
	    /* 	emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_COMMAND; */
	    /* 	tpAbort(&emcmotDebug->queue); */
	    /* 	SET_MOTION_ERROR_FLAG(1); */
	    /* } else { */
	    emcmotStatus->spindle.speed = emcmotCommand->vel;
	    emcmotStatus->spindle.css_factor = emcmotCommand->ini_maxvel;
	    emcmotStatus->spindle.xoffset = emcmotCommand->acc;
	    if (emcmotCommand->vel >= 0) {
		emcmotStatus->spindle.direction = 1;
	    } else {
		emcmotStatus->spindle.direction = -1;
	    }
	    emcmotStatus->spindle.brake = 0; //disengage brake
	    emcmotStatus->atspeed_next_feed = 1;
	    break;

	case EMCMOT_SPINDLE_OFF:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE_OFF");
	    emcmotStatus->spindle.speed = 0;
	    emcmotStatus->spindle.direction = 0;
	    emcmotStatus->spindle.brake = 1; // engage brake
	    if (*(emcmot_hal_data->spindle_orient))
		rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE_ORIENT cancelled by SPINDLE_OFF");
	    if (*(emcmot_hal_data->spindle_locked))
		rtapi_print_msg(RTAPI_MSG_DBG, "spindle-locked cleared by SPINDLE_OFF");
	    *(emcmot_hal_data->spindle_locked) = 0;
	    *(emcmot_hal_data->spindle_orient) = 0;
	    emcmotStatus->spindle.orient_state = EMCMOT_ORIENT_NONE;
	    break;

	case EMCMOT_SPINDLE_ORIENT:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE_ORIENT");
	    if (*(emcmot_hal_data->spindle_orient)) {
		rtapi_print_msg(RTAPI_MSG_DBG, "orient already in progress");

		// mah:FIXME unsure wether this is ok or an error
		/* reportError(_("orient already in progress")); */
		/* emcmotStatus->commandStatus = EMCMOT_COMMAND_INVALID_COMMAND; */
		/* tpAbort(&emcmotDebug->queue); */
		/* SET_MOTION_ERROR_FLAG(1); */
	    }
	    emcmotStatus->spindle.orient_state = EMCMOT_ORIENT_IN_PROGRESS;
	    emcmotStatus->spindle.speed = 0;
	    emcmotStatus->spindle.direction = 0;
	    // so far like spindle stop, except opening brake
	    emcmotStatus->spindle.brake = 0; // open brake

	    *(emcmot_hal_data->spindle_orient_angle) = emcmotCommand->orientation;
	    *(emcmot_hal_data->spindle_orient_mode) = emcmotCommand->mode;
	    *(emcmot_hal_data->spindle_locked) = 0;
	    *(emcmot_hal_data->spindle_orient) = 1;

	    // mirror in spindle status
	    emcmotStatus->spindle.orient_fault = 0; // this pin read during spindle-orient == 1 
	    emcmotStatus->spindle.locked = 0;
	    break;

	case EMCMOT_SPINDLE_INCREASE:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE_INCREASE");
	    if (emcmotStatus->spindle.speed > 0) {
		emcmotStatus->spindle.speed += 100; //FIXME - make the step a HAL parameter
	    } else if (emcmotStatus->spindle.speed < 0) {
		emcmotStatus->spindle.speed -= 100;
	    }
	    break;

	case EMCMOT_SPINDLE_DECREASE:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE_DECREASE");
	    if (emcmotStatus->spindle.speed > 100) {
		emcmotStatus->spindle.speed -= 100; //FIXME - make the step a HAL parameter
	    } else if (emcmotStatus->spindle.speed < -100) {
		emcmotStatus->spindle.speed += 100;
	    }
	    break;

	case EMCMOT_SPINDLE_BRAKE_ENGAGE:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE_BRAKE_ENGAGE");
	    emcmotStatus->spindle.speed = 0;
	    emcmotStatus->spindle.direction = 0;
	    emcmotStatus->spindle.brake = 1;
	    break;

	case EMCMOT_SPINDLE_BRAKE_RELEASE:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SPINDLE_BRAKE_RELEASE");
	    emcmotStatus->spindle.brake = 0;
	    break;

	case EMCMOT_SET_JOINT_COMP:
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_JOINT_COMP for joint %d", joint_num);
	    if (joint == 0) {
		break;
	    }
	    if (joint->comp.entries >= EMCMOT_COMP_SIZE) {
		reportError(_("joint %d: too many compensation entries"), joint_num);
		break;
	    }
	    /* point to last entry */
	    comp_entry = &(joint->comp.array[joint->comp.entries]);
	    if (emcmotCommand->comp_nominal <= comp_entry[0].nominal) {
		reportError(_("joint %d: compensation values must increase"), joint_num);
		break;
	    }
	    /* store data to new entry */
	    comp_entry[1].nominal = emcmotCommand->comp_nominal;
	    comp_entry[1].fwd_trim = emcmotCommand->comp_forward;
	    comp_entry[1].rev_trim = emcmotCommand->comp_reverse;
	    /* calculate slopes from previous entry to the new one */
	    if ( comp_entry[0].nominal != -DBL_MAX ) {
		/* but only if the previous entry is "real" */
		tmp1 = comp_entry[1].nominal - comp_entry[0].nominal;
		comp_entry[0].fwd_slope =
		    (comp_entry[1].fwd_trim - comp_entry[0].fwd_trim) / tmp1;
		comp_entry[0].rev_slope =
		    (comp_entry[1].rev_trim - comp_entry[0].rev_trim) / tmp1;
	    } else {
		/* previous entry is at minus infinity, slopes are zero */
		comp_entry[0].fwd_trim = comp_entry[1].fwd_trim;
		comp_entry[0].rev_trim = comp_entry[1].rev_trim;
	    }
	    joint->comp.entries++;
	    break;

        case EMCMOT_SET_OFFSET:
            emcmotStatus->tool_offset = emcmotCommand->tool_offset;
            break;

	case EMCMOT_SET_AXIS_POSITION_LIMITS:
	    /* set the position limits for axis */
	    /* can be done at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_AXIS_POSITION_LIMITS");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d", axis_num);
	    emcmot_config_change();
	    if (axis == 0) {
		break;
	    }
	    axis->min_pos_limit = emcmotCommand->minLimit;
	    axis->max_pos_limit = emcmotCommand->maxLimit;
	    break;

        case EMCMOT_SET_AXIS_VEL_LIMIT:
	    /* set the max axis vel */
	    /* can be done at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_AXIS_VEL_LIMITS");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d vel(%f)", axis_num, emcmotCommand->vel);
	    emcmot_config_change();
	    if (axis == 0) {
		break;
	    }
	    axis->vel_limit = emcmotCommand->vel;
            break;

        case EMCMOT_SET_AXIS_ACC_LIMIT:
 	    /* set the max axis acc */
	    /* can be done at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_AXIS_ACC_LIMITS");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d acc(%f)", axis_num, emcmotCommand->acc);
	    emcmot_config_change();
	    if (axis == 0) {
		break;
	    }
	    axis->acc_limit = emcmotCommand->acc;
            break;

        case EMCMOT_SET_AXIS_JERK_LIMIT:
 	    /* set the max axis jerk */
	    /* can be done at any time */
	    rtapi_print_msg(RTAPI_MSG_DBG, "SET_AXIS_JERK_LIMITS");
	    rtapi_print_msg(RTAPI_MSG_DBG, " %d jerk(%f)", axis_num, emcmotCommand->jerk);
	    emcmot_config_change();
	    if (axis == 0) {
		break;
	    }
	    axis->jerk_limit = emcmotCommand->jerk;
            break;

	default:
	    rtapi_print_msg(RTAPI_MSG_DBG, "UNKNOWN");
	    reportError(_("unrecognized command %d"), emcmotCommand->command);
	    emcmotStatus->commandStatus = EMCMOT_COMMAND_UNKNOWN_COMMAND;
	    break;

	}			/* end of: command switch */
	if (emcmotStatus->commandStatus != EMCMOT_COMMAND_OK) {
	    rtapi_print_msg(RTAPI_MSG_DBG, "ERROR: %d",
		emcmotStatus->commandStatus);
	}
	rtapi_print_msg(RTAPI_MSG_DBG, "\n");
	/* synch tail count */
	emcmotStatus->tail = emcmotStatus->head;
	emcmotConfig->tail = emcmotConfig->head;
	emcmotDebug->tail = emcmotDebug->head;

    }
    /* end of: if-new-command */
    check_stuff ( "after command_handler()" );
    rtapi_set_msg_level(msg_level_before);
    return;
}
