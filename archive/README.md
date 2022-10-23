# ohmywod
WoD greasemonkey scripts for fun : )

item_records_gen usage:

使用方法：

    1. 编辑团队论坛中复制自[post:15875563]的帖子，将 bbcode 复制粘贴至本地文件 /tmp/item_records_bbcode.txt
    2. 在 英雄 → 装备 → 宝库 和 英雄 → 装备 → 团队仓库 直接点击搜索列出所有物品，然后点击右上角 csv 导出 csv 文件存为本地文件，分别为 ~/Downloads/group_treasure.csv 和 ~/Downloads/group_cellar.csv
    3. 运行上述脚本

    ./item_records_gen ~/Downloads/group_treasure.csv ~/Downloads/group_cellar.csv /tmp/item_records_bbcode.txt > /tmp/output.txt
    pbcopy < /tmp/output.txt  # 将输出内容复制到剪贴板中

    4. 将生成的内容粘贴至被编辑的帖子中，提交。已有物品被被自动标记为青绿色
