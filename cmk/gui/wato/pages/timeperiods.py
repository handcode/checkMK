#!/usr/bin/env python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
# |           | |___| | | |  __/ (__|   <    | |  | | . \            |
# |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
# |                                                                  |
# | Copyright Mathias Kettner 2014             mk@mathias-kettner.de |
# +------------------------------------------------------------------+
#
# This file is part of Check_MK.
# The official homepage is at http://mathias-kettner.de/check_mk.
#
# check_mk is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 2.  check_mk is  distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# tails. You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

"""Modes for managing timeperiod definitions for the core"""

import re
import time

import cmk.gui.config as config
import cmk.gui.watolib as watolib
import cmk.gui.userdb as userdb
import cmk.gui.table as table
import cmk.gui.forms as forms
import cmk.gui.plugins.wato.utils
import cmk.gui.wato.mkeventd
from cmk.gui.exceptions import MKUserError
from cmk.gui.i18n import _
from cmk.gui.globals import html
from cmk.gui.valuespec import (
    Dictionary,
    Optional,
    Integer,
    FileUpload,
    TextAscii,
    ListOf,
    Tuple,
    ValueSpec,
    TimeofdayRange,
    ListChoice,
)

from cmk.gui.plugins.wato import (
    WatoMode,
    wato_confirm,
    global_buttons,
    mode_registry,
    make_action_link,
)


@mode_registry.register
class ModeTimeperiods(WatoMode):
    @classmethod
    def name(cls):
        return "timeperiods"


    @classmethod
    def permissions(cls):
        return ["timeperiods"]


    def __init__(self):
        super(ModeTimeperiods, self).__init__()
        self._timeperiods = watolib.load_timeperiods()


    def title(self):
        return _("Timeperiods")


    def buttons(self):
        global_buttons()
        html.context_button(_("New Timeperiod"), watolib.folder_preserving_link([("mode", "edit_timeperiod")]), "new")
        html.context_button(_("Import iCalendar"), watolib.folder_preserving_link([("mode", "import_ical")]), "ical")


    def action(self):
        delname = html.var("_delete")
        if delname and html.transaction_valid():
            usages = self._find_usages_of_timeperiod(delname)
            if usages:
                message = "<b>%s</b><br>%s:<ul>" % \
                            (_("You cannot delete this timeperiod."),
                             _("It is still in use by"))
                for title, link in usages:
                    message += '<li><a href="%s">%s</a></li>\n' % (link, title)
                message += "</ul>"
                raise MKUserError(None, message)

            c = wato_confirm(_("Confirm deletion of time period %s") % delname,
                  _("Do you really want to delete the time period '%s'? I've checked it: "
                    "it is not being used by any rule or user profile right now.") % delname)
            if c:
                del self._timeperiods[delname]
                watolib.save_timeperiods(self._timeperiods)
                watolib.add_change("edit-timeperiods", _("Deleted timeperiod %s") % delname)
            elif c == False:
                return ""


    # Check if a timeperiod is currently in use and cannot be deleted
    # Returns a list of two element tuples (title, url) that refer to the single occurrances.
    #
    # Possible usages:
    # - 1. rules: service/host-notification/check-period
    # - 2. user accounts (notification period)
    # - 3. excluded by other timeperiods
    # - 4. timeperiod condition in notification and alerting rules
    # - 5. bulk operation in notification rules
    # - 6. timeperiod condition in EC rules
    # - 7. rules: time specific parameters
    def _find_usages_of_timeperiod(self, tpname):
        used_in = []
        used_in += self._find_usages_in_host_and_service_rules(tpname)
        used_in += self._find_usages_in_users(tpname)
        used_in += self._find_usages_in_other_timeperiods(tpname)
        used_in += self._find_usages_in_notification_rules(tpname)
        used_in += self._find_usages_in_alert_handler_rules(tpname)
        used_in += self._find_usages_in_ec_rules(tpname)
        used_in += self._find_usages_in_time_specific_parameters(tpname)
        return used_in


    def _find_usages_in_host_and_service_rules(self, tpname):
        used_in = []
        rulesets = watolib.AllRulesets()
        rulesets.load()

        for varname, ruleset in rulesets.get_rulesets().items():
            if not isinstance(ruleset.valuespec(), watolib.TimeperiodSelection):
                continue

            for _folder, _rulenr, rule in ruleset.get_rules():
                if rule.value == tpname:
                    used_in.append(("%s: %s" % (_("Ruleset"), ruleset.title()),
                                   watolib.folder_preserving_link([("mode", "edit_ruleset"), ("varname", varname)])))
                    break

        return used_in


    def _find_usages_in_users(self, tpname):
        used_in = []
        for userid, user in userdb.load_users().items():
            tp = user.get("notification_period")
            if tp == tpname:
                used_in.append(("%s: %s" % (_("User"), userid),
                    watolib.folder_preserving_link([("mode", "edit_user"), ("edit", userid)])))

            for index, rule in enumerate(user.get("notification_rules", [])):
                used_in += self._find_usages_in_notification_rule(tpname, index, rule, user_id=userid)
        return used_in


    def _find_usages_in_other_timeperiods(self, tpname):
        used_in = []
        for tpn, tp in watolib.load_timeperiods().items():
            if tpname in tp.get("exclude", []):
                used_in.append(("%s: %s (%s)" % (_("Timeperiod"), tp.get("alias", tpn),
                        _("excluded")),
                        watolib.folder_preserving_link([("mode", "edit_timeperiod"), ("edit", tpn)])))
        return used_in


    def _find_usages_in_notification_rules(self, tpname):
        used_in = []
        for index, rule in enumerate(watolib.load_notification_rules()):
            used_in += self._find_usages_in_notification_rule(tpname, index, rule)
        return used_in


    def _find_usages_in_notification_rule(self, tpname, index, rule, user_id=None):
        used_in = []

        if self._used_in_tp_condition(rule, tpname) or self._used_in_bulking(rule, tpname):
            url = watolib.folder_preserving_link([("mode", "notification_rule"), ("edit", index), ("user", user_id)])
            if user_id:
                title = _("Notification rule of user '%s'") % user_id
            else:
                title = _("Notification rule")

            used_in.append((title, url))

        return used_in


    def _used_in_tp_condition(self, rule, tpname):
        return rule.get("match_timeperiod") == tpname


    def _used_in_bulking(self, rule, tpname):
        bulk = rule.get("bulk")
        if isinstance(bulk, tuple):
            method, params = bulk
            return method == "timeperiod" and params["timeperiod"] == tpname
        return False


    def _find_usages_in_alert_handler_rules(self, tpname):
        used_in = []

        if cmk.is_raw_edition():
            return used_in

        try:
            import cmk.gui.cee.plugins.wato.alert_handling as alert_handling
        except:
            alert_handling = None

        for index, rule in enumerate(alert_handling.load_alert_handler_rules()):
            if rule.get("match_timeperiod") == tpname:
                url = watolib.folder_preserving_link([("mode", "alert_handler_rule"), ("edit", index)])
                used_in.append((_("Alert handler rule"), url))
        return used_in


    def _find_usages_in_ec_rules(self, tpname):
        used_in = []
        rule_packs = cmk.gui.wato.mkeventd.load_mkeventd_rules()
        for rule_pack in rule_packs:
            for rule_index, rule in enumerate(rule_pack["rules"]):
                if rule.get("match_timeperiod") == tpname:
                    url = watolib.folder_preserving_link([("mode", "mkeventd_edit_rule"),
                                                          ("edit", rule_index),
                                                          ("rule_pack", rule_pack["id"])])
                    used_in.append((_("Event console rule"), url))
        return used_in


    def _find_usages_in_time_specific_parameters(self, tpname):
        used_in = []
        rulesets = watolib.AllRulesets()
        rulesets.load()
        for ruleset in rulesets.get_rulesets().values():
            vs = ruleset.valuespec()
            if not isinstance(vs, cmk.gui.plugins.wato.utils.TimeperiodValuespec):
                continue

            for rule_folder, rule_index, rule in ruleset.get_rules():
                if not vs.is_active(rule.value):
                    continue

                for index, (rule_tp_name, _value) in enumerate(rule.value["tp_values"]):
                    if rule_tp_name != tpname:
                        continue

                    edit_url = watolib.folder_preserving_link([
                        ("mode", "edit_rule"),
                        ("back_mode", "timeperiods"),
                        ("varname", ruleset.name),
                        ("rulenr", rule_index),
                        ("rule_folder", rule_folder.path()),
                    ])
                    used_in.append((_("Time specific check parameter #%d") % (index + 1), edit_url))

        return used_in


    def page(self):
        table.begin("timeperiods", empty_text = _("There are no timeperiods defined yet."))
        for name in sorted(self._timeperiods.keys()):
            table.row()

            timeperiod = self._timeperiods[name]
            edit_url     = watolib.folder_preserving_link([("mode", "edit_timeperiod"), ("edit", name)])
            delete_url   = make_action_link([("mode", "timeperiods"), ("_delete", name)])

            table.cell(_("Actions"), css="buttons")
            html.icon_button(edit_url, _("Properties"), "edit")
            html.icon_button(delete_url, _("Delete"), "delete")

            table.text_cell(_("Name"), name)
            table.text_cell(_("Alias"), timeperiod.get("alias", ""))
        table.end()



class MultipleTimeRanges(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._num_columns = kwargs.get("num_columns", 3)
        self._rangevs = TimeofdayRange()

    def canonical_value(self):
        return [ ((0,0), (24,0)), None, None ]

    def render_input(self, varprefix, value):
        for c in range(0, self._num_columns):
            if c:
                html.write(" &nbsp; ")
            if c < len(value):
                v = value[c]
            else:
                v = self._rangevs.canonical_value()
            self._rangevs.render_input(varprefix + "_%d" % c, v)

    def value_to_text(self, value):
        parts = []
        for v in value:
            parts.append(self._rangevs.value_to_text(v))
        return ", ".join(parts)

    def from_html_vars(self, varprefix):
        value = []
        for c in range(0, self._num_columns):
            v = self._rangevs.from_html_vars(varprefix + "_%d" % c)
            if v != None:
                value.append(v)
        return value

    def validate_value(self, value, varprefix):
        for c, v in enumerate(value):
            self._rangevs.validate_value(v, varprefix + "_%d" % c)
        ValueSpec.custom_validate(self, value, varprefix)


# Displays a dialog for uploading an ical file which will then
# be used to generate timeperiod exceptions etc. and then finally
# open the edit_timeperiod page to create a new timeperiod using
# these information
@mode_registry.register
class ModeTimeperiodImportICal(WatoMode):
    @classmethod
    def name(cls):
        return "import_ical"


    @classmethod
    def permissions(cls):
        return ["timeperiods"]


    def title(self):
        return _("Import iCalendar File to create a Timeperiod")


    def buttons(self):
        html.context_button(_("All Timeperiods"),
            watolib.folder_preserving_link([("mode", "timeperiods")]), "back")


    def _vs_ical(self):
        return Dictionary(
            title = _('Import iCalendar File'),
            render = "form",
            optional_keys = None,
            elements = [
                ('file', FileUpload(
                    title = _('iCalendar File'),
                    help = _("Select an iCalendar file (<tt>*.ics</tt>) from your PC"),
                    allow_empty = False,
                    custom_validate = self._validate_ical_file,
                )),
                ('horizon', Integer(
                    title = _('Time horizon for repeated events'),
                    help = _("When the iCalendar file contains definitions of repeating events, these repeating "
                             "events will be resolved to single events for the number of years you specify here."),
                    minvalue = 0,
                    maxvalue = 50,
                    default_value = 10,
                    unit = _('years'),
                    allow_empty = False,
                )),
                ('times', Optional(
                    MultipleTimeRanges(
                        default_value = [None, None, None],
                    ),
                    title = _('Use specific times'),
                    label = _('Use specific times instead of whole day'),
                    help = _("When you specify explicit time definitions here, these will be added to each "
                             "date which is added to the resulting time period. By default the whole day is "
                             "used."),
                )),
            ]
        )


    def _validate_ical_file(self, value, varprefix):
        filename, _ty, content = value
        if not filename.endswith('.ics'):
            raise MKUserError(varprefix, _('The given file does not seem to be a valid iCalendar file. '
                                           'It needs to have the file extension <tt>.ics</tt>.'))

        if not content.startswith('BEGIN:VCALENDAR'):
            raise MKUserError(varprefix, _('The file does not seem to be a valid iCalendar file.'))

        if not content.startswith('END:VCALENDAR'):
            raise MKUserError(varprefix, _('The file does not seem to be a valid iCalendar file.'))


    def action(self):
        if not html.check_transaction():
            return

        vs_ical = self._vs_ical()
        ical = vs_ical.from_html_vars("ical")
        vs_ical.validate_value(ical, "ical")

        filename, _ty, content = ical['file']

        try:
            data = self._parse_ical(content, ical['horizon'])
        except Exception, e:
            if config.debug:
                raise
            raise MKUserError('ical_file', _('Failed to parse file: %s') % e)

        html.set_var('alias', data.get('descr', data.get('name', filename)))

        for day in [ "monday", "tuesday", "wednesday", "thursday",
                     "friday", "saturday", "sunday" ]:
            html.set_var('%s_0_from' % day, '')
            html.set_var('%s_0_until' % day, '')

        html.set_var('except_count', "%d" % len(data['events']))
        for index, event in enumerate(data['events']):
            index += 1
            html.set_var('except_%d_0' % index, event['date'])
            html.set_var('except_indexof_%d' % index, "%d" % index)

            if ical["times"]:
                for n, time_spec in enumerate(ical["times"]):
                    start_time = ":".join("%02d" % x for x in time_spec[0])
                    end_time   = ":".join("%02d" % x for x in time_spec[1])
                    html.set_var('except_%d_1_%d_from' % (index, n), start_time)
                    html.set_var('except_%d_1_%d_until' % (index, n), end_time)

        return "edit_timeperiod"


    # Returns a dictionary in the format:
    # {
    #   'name'   : '...',
    #   'descr'  : '...',
    #   'events' : [
    #       {
    #           'name': '...',
    #           'date': '...',
    #       },
    #   ],
    # }
    #
    # Relevant format specifications:
    #   http://tools.ietf.org/html/rfc2445
    #   http://tools.ietf.org/html/rfc5545
    # TODO: Let's use some sort of standard module in the future. Maybe we can then also handle
    # times instead of only full day events.
    def _parse_ical(self, ical_blob, horizon=10):
        ical = {'raw_events': []}

        def get_params(key):
            if ';' in key:
                return dict([ p.split('=', 1) for p in key.split(';')[1:] ])
            return {}

        def parse_date(params, val):
            # First noprmalize the date value to make it easier parsable later
            if 'T' not in val and params.get('VALUE') == 'DATE':
                val += 'T000000' # add 00:00:00 to date specification

            return list(time.strptime(val, '%Y%m%dT%H%M%S'))

        # First extract the relevant information from the file
        in_event = False
        event    = {}
        for l in ical_blob.split('\n'):
            line = l.strip()
            if not line:
                continue
            try:
                key, val = line.split(':', 1)
            except ValueError:
                raise Exception('Failed to parse line: %r' % line)

            if key == 'X-WR-CALNAME':
                ical['name'] = val
            elif key == 'X-WR-CALDESC':
                ical['descr'] = val

            elif line == 'BEGIN:VEVENT':
                in_event = True
                event = {} # create new event

            elif line == 'END:VEVENT':
                # Finish the current event
                ical['raw_events'].append(event)
                in_event = False

            elif in_event:
                if key.startswith('DTSTART'):
                    params = get_params(key)
                    event['start'] = parse_date(params, val)

                elif key.startswith('DTEND'):
                    params = get_params(key)
                    event['end'] = parse_date(params, val)

                elif key == 'RRULE':
                    event['recurrence'] = dict([ p.split('=', 1) for p in val.split(';') ])

                elif key == 'SUMMARY':
                    event['name'] = val

        def next_occurrence(start, now, freq):
            # convert struct_time to list to be able to modify it,
            # then set it to the next occurence
            t = start[:]

            if freq == 'YEARLY':
                t[0] = now[0]+1 # add 1 year
            elif freq == 'MONTHLY':
                if now[1] + 1 > 12:
                    t[0] = now[0]+1
                    t[1] = now[1] + 1 - 12
                else:
                    t[0] = now[0]
                    t[1] = now[1] + 1
            else:
                raise Exception('The frequency "%s" is currently not supported' % freq)
            return t

        def resolve_multiple_days(event, cur_start_time):
            if time.strftime('%Y-%m-%d', cur_start_time) \
                == time.strftime('%Y-%m-%d', event["end"]):
                # Simple case: a single day event
                return [{
                    'name'  : event['name'],
                    'date'  : time.strftime('%Y-%m-%d', cur_start_time),
                }]

            # Resolve multiple days
            resolved, cur_timestamp, day = [], time.mktime(cur_start_time), 1
            # day < 100 is just some plausibilty check. In case such an event
            # is needed eventually remove this
            while cur_timestamp < time.mktime(event["end"]) and day < 100:
                resolved.append({
                    "name" : "%s %s" % (event["name"], _(" (day %d)") % day),
                    "date" : time.strftime("%Y-%m-%d", time.localtime(cur_timestamp)),
                })
                cur_timestamp += 86400
                day += 1

            return resolved

        # Now resolve recurring events starting from 01.01 of current year
        # Non-recurring events are simply copied
        resolved = []
        now  = list(time.strptime(str(time.localtime().tm_year-1), "%Y"))
        last = now[:]
        last[0] += horizon+1 # update year to horizon
        for event in ical['raw_events']:
            if 'recurrence' in event and event['start'] < now:
                rule     = event['recurrence']
                freq     = rule['FREQ']
                cur      = now
                while cur < last:
                    cur = next_occurrence(event['start'], cur, freq)
                    resolved += resolve_multiple_days(event, cur)
            else:
                resolved += resolve_multiple_days(event, event["start"])

        ical['events'] = sorted(resolved)

        return ical


    def page(self):
        html.p(_('This page can be used to generate a new timeperiod definition based '
                 'on the appointments of an iCalendar (<tt>*.ics</tt>) file. This import is normally used '
                 'to import events like holidays, therefore only single whole day appointments are '
                 'handled by this import.'))

        html.begin_form("import_ical", method="POST")
        self._vs_ical().render_input("ical", {})
        forms.end()
        html.button("upload", _("Import"))
        html.hidden_fields()
        html.end_form()



@mode_registry.register
class ModeEditTimeperiod(WatoMode):
    @classmethod
    def name(cls):
        return "edit_timeperiod"


    @classmethod
    def permissions(cls):
        return ["timeperiods"]


    def _from_vars(self):
        self._timeperiods = watolib.load_timeperiods()
        self._name = html.var("edit") # missing -> new group

        if self._name == None:
            self._new  = True
            self._timeperiod = {}
        else:
            self._new  = False

            try:
                self._timeperiod = self._timeperiods[self._name]
            except KeyError:
                raise MKUserError(None, _("This timeperiod does not exist."))


    def _convert_from_range(self, rng):
        # ("00:30", "10:17") -> ((0,30),(10,17))
        return tuple(map(self._convert_from_tod, rng))


    # convert Check_MK representation of range to ValueSpec-representation
    def _convert_from_tod(self, tod):
        # "00:30" -> (0, 30)
        return tuple(map(int, tod.split(":")))


    def _convert_to_range(self, value):
        return tuple(map(self._convert_to_tod, value))


    def _convert_to_tod(self, value):
        return "%02d:%02d" % value


    def title(self):
        if self._new:
            return _("Create new time period")
        else:
            return _("Edit time period")


    def buttons(self):
        html.context_button(_("All Timeperiods"), watolib.folder_preserving_link([("mode", "timeperiods")]), "back")


    def _vs_exceptions(self):
        return ListOf(
            Tuple(
                orientation = "horizontal",
                show_titles = False,
                elements = [
                    TextAscii(
                        regex = "^[-a-z0-9A-Z /]*$",
                        regex_error = _("This is not a valid Nagios timeperiod day specification."),
                        allow_empty = False,
                        validate = self._validate_timeperiod_exception,
                    ),
                    MultipleTimeRanges()
                ],
            ),
            movable = False,
            add_label = _("Add Exception")
        )


    def _validate_timeperiod_exception(self, value, varprefix):
        if value in [ "monday", "tuesday", "wednesday", "thursday",
                       "friday", "saturday", "sunday" ]:
            raise MKUserError(varprefix, _("You cannot use weekday names (%s) in exceptions") % value)

        if value in [ "name", "alias", "timeperiod_name", "register", "use", "exclude" ]:
            raise MKUserError(varprefix, _("<tt>%s</tt> is a reserved keyword."))


    def _vs_excludes(self):
        return ListChoice(choices=self._other_timeperiods())


    def _other_timeperiods(self):
        # ValueSpec for excluded Timeperiods. We offer the list of
        # all other timeperiods - but only those that do not
        # exclude the current timeperiod (in order to avoid cycles)
        other_tps = []
        for tpname, tp in self._timeperiods.items():
            if not self._timeperiod_excludes(tpname):
                other_tps.append((tpname, tp.get("alias") or self._name))
        return other_tps


    # Check, if timeperiod tpa excludes or is tpb
    def _timeperiod_excludes(self, tpa_name):
        if tpa_name == self._name:
            return True

        tpa = self._timeperiods[tpa_name]
        for ex in tpa.get("exclude", []):
            if ex == self._name:
                return True

            if self._timeperiod_excludes(ex):
                return True

        return False


    def action(self):
        if not html.check_transaction():
            return

        alias = html.get_unicode_input("alias").strip()
        if not alias:
            raise MKUserError("alias", _("Please specify an alias name for your timeperiod."))

        unique, info = watolib.is_alias_used("timeperiods", self._name, alias)
        if not unique:
            raise MKUserError("alias", info)

        self._timeperiod.clear()

        # extract time ranges of weekdays
        for weekday, _weekday_name in self._weekdays_by_name():
            ranges = self._get_ranges(weekday)
            if ranges:
                self._timeperiod[weekday] = ranges
            elif weekday in self._timeperiod:
                del self._timeperiod[weekday]

        # extract ranges for custom days
        vs_ex = self._vs_exceptions()
        exceptions = vs_ex.from_html_vars("except")
        vs_ex.validate_value(exceptions, "except")
        for exname, ranges in exceptions:
            self._timeperiod[exname] = map(self._convert_to_range, ranges)

        # extract excludes
        vs_excl = self._vs_excludes()
        excludes = vs_excl.from_html_vars("exclude")
        vs_excl.validate_value(excludes, "exclude")
        if excludes:
            self._timeperiod["exclude"] = excludes

        if self._new:
            name = html.var("name")
            if len(name) == 0:
                raise MKUserError("name", _("Please specify a name of the new timeperiod."))
            if not re.match("^[-a-z0-9A-Z_]*$", name):
                raise MKUserError("name", _("Invalid timeperiod name. Only the characters a-z, A-Z, 0-9, _ and - are allowed."))
            if name in self._timeperiods:
                raise MKUserError("name", _("This name is already being used by another timeperiod."))
            if name == "24X7":
                raise MKUserError("name", _("The time period name 24X7 cannot be used. It is always autmatically defined."))
            self._timeperiods[name] = self._timeperiod
            watolib.add_change("edit-timeperiods", _("Created new time period %s") % name)
        else:
            watolib.add_change("edit-timeperiods", _("Modified time period %s") % self._name)

        self._timeperiod["alias"] = alias
        watolib.save_timeperiods(self._timeperiods)
        return "timeperiods"


    def _get_ranges(self, varprefix):
        value = MultipleTimeRanges().from_html_vars(varprefix)
        MultipleTimeRanges().validate_value(value, varprefix)
        return map(self._convert_to_range, value)


    def page(self):
        html.begin_form("timeperiod", method="POST")
        forms.header(_("Timeperiod"))

        # Name
        forms.section(_("Internal name"), simple = not self._new)
        if self._new:
            html.text_input("name")
            html.set_focus("name")
        else:
            html.write_text(self._name)

        # Alias
        if not self._new:
            alias = self._timeperiod.get("alias", "")
        else:
            alias = ""

        forms.section(_("Alias"))
        html.help(_("An alias or description of the timeperiod"))
        html.text_input("alias", alias, size = 81)
        if not self._new:
            html.set_focus("alias")

        # Week days
        forms.section(_("Weekdays"))
        html.help("For each weekday you can setup no, one or several "
                   "time ranges in the format <tt>23:39</tt>, in which the time period "
                   "should be active.")
        html.open_table(class_="timeperiod")

        for weekday, weekday_alias in self._weekdays_by_name():
            html.open_tr()
            html.td(weekday_alias, class_="name")
            self._timeperiod_ranges(weekday, weekday)
            html.close_tr()
        html.close_table()

        # Exceptions
        forms.section(_("Exceptions (from weekdays)"))
        html.help(_("Here you can specify exceptional time ranges for certain "
                    "dates in the form YYYY-MM-DD which are used to define more "
                    "specific definitions to override the times configured for the matching "
                    "weekday."))

        exceptions = []
        for k in self._timeperiod:
            if k not in [ w[0] for w in self._weekdays_by_name() ] and k not in [ "alias", "exclude" ]:
                exceptions.append((k, map(self._convert_from_range, self._timeperiod[k])))
        exceptions.sort()
        self._vs_exceptions().render_input("except", exceptions)

        # Excludes
        if self._other_timeperiods():
            forms.section(_("Exclude"))
            html.help(_('You can use other timeperiod definitions to exclude the times '
                        'defined in the other timeperiods from this current timeperiod.'))
            self._vs_excludes().render_input("exclude", self._timeperiod.get("exclude", []))


        forms.end()
        html.button("save", _("Save"))
        html.hidden_fields()
        html.end_form()


    def _timeperiod_ranges(self, vp, keyname):
        ranges = self._timeperiod.get(keyname, [])
        value = []
        for rng in ranges:
            value.append(self._convert_from_range(rng))

        if len(value) == 0 and self._new:
            value.append(((0,0), (24,0)))

        html.open_td()
        MultipleTimeRanges().render_input(vp, value)
        html.close_td()


    def _weekdays_by_name(self):
        return [
           ( "monday",    _("Monday") ),
           ( "tuesday",   _("Tuesday") ),
           ( "wednesday", _("Wednesday") ),
           ( "thursday",  _("Thursday") ),
           ( "friday",    _("Friday") ),
           ( "saturday",  _("Saturday") ),
           ( "sunday",    _("Sunday") ),
        ]
