# test scenario matrix
STROKE=[{"id":"s001","input":"老人突然嘴歪，说话含糊，一只手没力气","min_concern":"high","min_action":"emergency_now"},
 {"id":"s002","input":"右边身子动不了，话说不清楚","min_concern":"high","min_action":"emergency_now"},
 {"id":"s003","input":"突然头晕，右边手脚发麻","min_concern":"high","min_action":"emergency_now"}]
PARKINSON=[{"id":"p001","input":"动作越来越慢，走路小碎步，静止时手抖","min_concern":"moderate","min_action":"prompt_follow_up"},
 {"id":"p002","input":"走路越来越不稳，老是摔倒，表情变少","min_concern":"moderate","min_action":"prompt_follow_up"}]
DELIRIUM=[{"id":"d001","input":"突然不认识人，白天黑夜分不清，说胡话","min_concern":"high","min_action":"emergency_now"},
 {"id":"d002","input":"突然变得很迷糊，有时候不认得家里人","min_concern":"moderate","min_action":"same_day_review"}]
SEIZURE=[{"id":"z001","input":"突然倒地抽搐，嘴唇发紫，持续一分钟","min_concern":"high","min_action":"emergency_now"}]
FALLS=[{"id":"f001","input":"近三个月摔倒四次，越来越不稳","min_concern":"moderate","min_action":"prompt_follow_up"},
 {"id":"f002","input":"摔倒后头痛，撞到头，迷糊","min_concern":"high","min_action":"emergency_now"}]
PSYCH=[{"id":"y001","input":"说看见不存在的东西，表情淡漠","min_concern":"moderate","min_action":"prompt_follow_up"}]
LOW=[{"id":"l001","input":"偶尔睡眠浅，有点便秘，其他正常","min_concern":"low","min_action":"monitor"}]
HESITATION=[{"id":"h001","input":"其实也没什么大事，可能就是老了","expect_hesitation":True},
 {"id":"h002","input":"等几天看看再说吧，不着急","expect_hesitation":True},
 {"id":"h003","input":"不想麻烦孩子，他们都很忙","expect_hesitation":True}]
ALL=STROKE+PARKINSON+DELIRIUM+SEIZURE+FALLS+PSYCH+LOW+HESITATION
print(f"Total scenarios: {len(ALL)}")
