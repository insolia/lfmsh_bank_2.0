import functools
from django.contrib.auth.models import User

from bank.constants import UserGroups, Actions, States, AttendanceTypeEnum, STUDY_NEEDED, LAB_PASS_NEEDED, \
    FAC_PASS_NEEDED
from bank.helper_functions import get_perm_name, get_next_missed_lec_penalty, get_students_markup
from bank.models import Money, Account, Transaction, Attendance, AttendanceType
import statistics


def get_student_stats(user):
    stats = {}

    if user.has_perm(get_perm_name(Actions.see.value, UserGroups.student.value, "balance")):
        student_accounts = Account.objects.filter(user__groups__name__contains=UserGroups.student.value)
        balances = [a.balance for a in student_accounts]
        stats.update({
            'sum_money': int(sum(balances)),
            'mean_money': int(statistics.mean(balances))
        })

        print(stats)

    if user.has_perm(get_perm_name(Actions.process.value, UserGroups.student.value, "created_transactions")):
        stats.update({'created_students_len': Transaction.objects.filter(
            creator__groups__name__in=[UserGroups.student.value]).filter(state__name=States.created.value).__len__()})

    if user.has_perm(get_perm_name(Actions.process.value, UserGroups.staff.value, "created_transactions")):
        stats.update({'created_staff_len': Transaction.objects.filter(
            creator__groups__name__in=[UserGroups.staff.value]).filter(state__name=States.created.value).__len__()})

    return stats


def get_report_student_stats(user):
    stats = {}

    if user.has_perm(get_perm_name(Actions.see.value, UserGroups.student.value, "balance")):
        student_accounts = Account.objects.filter(user__groups__name__contains=UserGroups.student.value).order_by(
            'party',
            'user__last_name')
        balances = [a.balance for a in student_accounts]
        stats.update({
            'sum_money': int(sum(balances)),
            'mean_money': int(statistics.mean(balances))
        })

        accounts_info = []
        for acc in student_accounts:
            money = acc.get_all_money()
            acc_info = {
                'acc': acc,
                'name': acc.long_name(),
                'str_balance': acc.get_balance(),
                'balance_stored': acc.balance,
                'party': acc.party,
                'balance_calculated': get_balance_change_from_money_list(money, acc.user.username),
                'earned_all': get_balance_change_from_money_list(
                    filter(lambda m: m.type.group_general not in ['fine', 'purchase', 'technicals'], money), acc.user.username),
                'earned_work': get_balance_change_from_money_list(
                    filter(lambda m: m.type.group_general == 'work', money), acc.user.username),
                'earned_fine': get_balance_change_from_money_list(
                    filter(lambda m: m.type.group_general == 'fine', money), acc.user.username),
                'earned_activity': get_balance_change_from_money_list(
                    filter(lambda m: m.type.group_general == 'activity', money), acc.user.username),
                'earned_sport': get_balance_change_from_money_list(
                    filter(lambda m: m.type.group_general == 'sport', money), acc.user.username),
                'earned_studies': get_balance_change_from_money_list(
                    filter(lambda m: m.type.group_general == 'studies', money), acc.user.username),
                'counters': get_counters_of_user_who_is(user, acc.user, UserGroups.student.value)
            }
            accounts_info.append(acc_info)

        best_activity = max(get_list_from_dict_list_by_key(accounts_info, 'earned_activity'))
        best_work = max(get_list_from_dict_list_by_key(accounts_info, 'earned_work'))
        best_sport = max(get_list_from_dict_list_by_key(accounts_info, 'earned_sport'))
        best_studies = max(get_list_from_dict_list_by_key(accounts_info, 'earned_studies'))
        best_all = max(get_list_from_dict_list_by_key(accounts_info, 'earned_all'))
        best_balance = max(get_list_from_dict_list_by_key(accounts_info, 'balance_stored'))

        for acc_info in accounts_info:
            acc_info['is_best_activity'] = acc_info['earned_activity'] == best_activity
            acc_info['is_best_work'] = acc_info['earned_work'] == best_work
            acc_info['is_best_sport'] = acc_info['earned_sport'] == best_sport
            acc_info['is_best_studies'] = acc_info['earned_studies'] == best_studies
            acc_info['is_best_all'] = acc_info['earned_all'] == best_all
            acc_info['is_best_balance'] = acc_info['balance_stored'] == best_balance


        stats.update({"accounts_info": accounts_info})

    return stats

def get_list_from_dict_list_by_key(dict_list, keyy):
    return [dict[keyy] for dict in dict_list]

def get_balance_change_from_money_list(money_list, username):
    r = 0
    for t in money_list:
        if t.counted:
            if t.receiver.username == username:
                r = r + t.value
            else:
                r = r - t.value

    return r


def get_counters_of_user_who_is(user, target_user, group):
    if not user.has_perm(get_perm_name(Actions.see.value, group, "attendance")):
        return None

    all_counters = Attendance.objects.filter(receiver=target_user).filter(counted=True)
    info = {"study_needed": STUDY_NEEDED, "fac_pass_needed": FAC_PASS_NEEDED.get(target_user.account.grade),
            "lab_pass_needed": LAB_PASS_NEEDED.get(target_user.account.grade)}
    counters_val = {}
    for counter_type in AttendanceType.objects.all():
        counter_sum = sum([c.value for c in all_counters.filter(type=counter_type)])
        counters_val.update({counter_type.name: int(counter_sum)})
    info.update({"study": counters_val.get(AttendanceTypeEnum.fac_attend.value) + counters_val.get(
        AttendanceTypeEnum.seminar_attend.value)})
    info.update(
        {"next_missed_lec_fine": get_next_missed_lec_penalty(counters_val.get(AttendanceTypeEnum.lecture_miss.value))})
    return {"val": counters_val, "info": info}
