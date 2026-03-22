# hesitation tests
from core.types import CaseState
from modules.hesitation_detector import detect_hesitation
def test_minimization():
    s=CaseState(raw_user_input="其实也没什么大事，可能就是老了。")
    f=detect_hesitation(s); assert "minimization" in f
def test_delay():
    s=CaseState(raw_user_input="等几天看看再说吧，不着急。")
    f=detect_hesitation(s); assert "delay" in f
def test_burden():
    s=CaseState(raw_user_input="我不想麻烦孩子，他们都很忙。")
    f=detect_hesitation(s); assert "burden" in f
def test_no_hesitation():
    s=CaseState(raw_user_input="我父亲突然右边身子动不了。")
    f=detect_hesitation(s); assert len(f)==0
