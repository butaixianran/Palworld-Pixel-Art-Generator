# 幻兽帕鲁 Pixel Art 生成器

修改幻兽帕鲁的存档文件，以存档中的玩家位置为起点，创建一个巨大的Pixel Art广告牌，来在游戏中显示你选择的任何图片

# 截图
![](screenshot/pixel_art_01.jpg)

![](screenshot/pixel_art_02.jpg)

![](screenshot/pixel_art_03.jpg)

![](screenshot/pixel_art_04.jpg)

![](screenshot/gui.jpg)

![](screenshot/gui2.jpg)

![](screenshot/i18n.jpg)

# 安装
* 只支持Steam
* Windows：从Release页面下载最新版，解压运行
* 其他平台：参考从源码运行的章节

# 准备

## 准备模板

进入游戏，确保在游戏中，存在未来风格地基、未来风格墙壁、玻璃立柱、玻璃墙壁至少各一个。

![](screenshot/prepare.jpg)

程序将复制他们的数据，作为模板，来创建新的地基、立柱和墙壁，而不是凭空创建。

因为这些数据太复杂了，每个字段都搞清楚会耗时耗力，而且结构还可能随着游戏更新而变化。复制游戏中存在的数据作为模板，是最方便的。

# 使用

## 游戏存档位置

```
%localappdata%\Pal\Saved\SaveGames\YOURID\RANDOMID\
```

## Windows
### 生成照片墙
* 确保Level.sav的目录下，有Players子目录。里面存放了角色信息，包括位置
* 运行程序，按照界面提示选择`Level.sav`存档文件。
* 等待加载角色列表，并选择角色
* 选择图片
* 点击最下方的执行按钮，等待结果。执行很慢，请耐心等待。
* App会自动备份原存档
* 进入游戏即可

### 清理照片墙
在App界面，输入要清理的半径范围。点击删除按钮，将修改存档，以人物为中心，删除半径范围内指定风格的地基、立柱、墙壁。


或者等待建筑随着时间自然损坏。


## 从源码运行
### 下载本项目源码
* 安装了git
  ```
  git clone https://github.com/butaixianran/Palworld-Pixel-Art-Generator
  ```

* 或者直接点击绿色Code菜单按钮，选择Download ZIP

### 安装环境
* 安装python，可以创建专用的虚拟环境。
* 安装C++编译环境。在Windows上是Visual Sutdio 2022，选择C++ Workload

### 安装本项目
* 命令行进入项目目录，进入src源码目录
* 运行：`pip install -r requirements.txt`

### 运行本项目
在src目录下：`python main.py`

# 参数说明
App界面上，已经对每个参数都进行了说明，这里只补充需要额外提到的。

* 最大宽度、最大高度：会自动保持图片比例，不会拉伸图片
* 透明像素：程序将使用玻璃墙面，并涂为黑色，来代表透明像素。黑色玻璃透明感最好。
