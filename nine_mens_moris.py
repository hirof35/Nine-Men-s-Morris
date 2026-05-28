import pygame
import sys
import math
import random

# --- 定数設定 ---
WIDTH, HEIGHT = 700, 700
BOARD_SIZE = 500
OFFSET = (WIDTH - BOARD_SIZE) // 2
CIRCLE_RADIUS = 22
FPS = 60

# 色定義
WHITE, BLACK = (255, 255, 255), (30, 30, 30)
RED, BLUE = (220, 50, 50), (50, 50, 220)
BEIGE, YELLOW = (245, 245, 220), (255, 255, 0)
GRAY = (150, 150, 150)

POSITIONS = [
    (0,0), (3,0), (6,0), (1,1), (3,1), (5,1), (2,2), (3,2), (4,2),
    (0,3), (1,3), (2,3), (4,3), (5,3), (6,3),
    (2,4), (3,4), (4,4), (1,5), (3,5), (5,5), (0,6), (3,6), (6,6)
]
SCREEN_POS = [(p[0]*BOARD_SIZE//6 + OFFSET, p[1]*BOARD_SIZE//6 + OFFSET) for p in POSITIONS]

ADJACENCY = {
    0:[1,9], 1:[0,2,4], 2:[1,14], 3:[4,10], 4:[1,3,5,7], 5:[4,13], 6:[7,11], 7:[4,6,8], 8:[7,12],
    9:[0,10,21], 10:[3,9,11,18], 11:[6,10,15], 12:[8,13,17], 13:[5,12,14,20], 14:[2,13,23],
    15:[11,16], 16:[15,17,19], 17:[12,16], 18:[10,19], 19:[16,18,20,22], 20:[13,19], 21:[9,22], 22:[19,21,23], 23:[14,22]
}

MILLS = [
    [0,1,2], [3,4,5], [6,7,8], [9,10,11], [12,13,14], [15,16,17], [18,19,20], [21,22,23],
    [0,9,21], [3,10,18], [6,11,15], [1,4,7], [16,19,22], [8,12,17], [5,13,20], [2,14,23]
]

# --- エフェクト系クラス ---
class SoundManager:
    def __init__(self):
        try:
            pygame.mixer.init()
            self.place = pygame.mixer.Sound("place.wav")
            self.mill = pygame.mixer.Sound("mill.wav")
            self.remove = pygame.mixer.Sound("remove.wav")
        except:
            self.place = self.mill = self.remove = None

    def play(self, name):
        s = getattr(self, name, None)
        if s: s.play()

class FadingPiece:
    def __init__(self, pos, color):
        self.pos = pos
        self.color = color
        self.alpha = 255
        self.active = True

    def update(self):
        self.alpha -= 10
        if self.alpha <= 0: self.active = False

    def draw(self, screen):
        s = pygame.Surface((CIRCLE_RADIUS*2, CIRCLE_RADIUS*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, self.alpha), (CIRCLE_RADIUS, CIRCLE_RADIUS), CIRCLE_RADIUS)
        screen.blit(s, (self.pos[0]-CIRCLE_RADIUS, self.pos[1]-CIRCLE_RADIUS))

class FlashingMill:
    def __init__(self, indices, color):
        self.indices = indices
        self.color = color
        self.frame = 0
        self.active = True

    def update(self):
        self.frame += 1
        if self.frame > 60: self.active = False

    def draw(self, screen):
        alpha = int(155 + 100 * math.sin(self.frame * 0.3))
        for idx in self.indices:
            s = pygame.Surface((CIRCLE_RADIUS*2, CIRCLE_RADIUS*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, alpha), (CIRCLE_RADIUS, CIRCLE_RADIUS), CIRCLE_RADIUS)
            pygame.draw.circle(s, (255, 255, 255, alpha), (CIRCLE_RADIUS, CIRCLE_RADIUS), CIRCLE_RADIUS, 3)
            screen.blit(s, (SCREEN_POS[idx][0]-CIRCLE_RADIUS, SCREEN_POS[idx][1]-CIRCLE_RADIUS))

# --- 🤖 難易度対応 AI クラス ---
class MorrisAI:
    def __init__(self, difficulty="NORMAL", ai_player=2):
        self.difficulty = difficulty
        self.ai_player = ai_player
        self.opp_player = 3 - ai_player

    def evaluate_board(self, board, phase):
        """盤面の評価関数"""
        score = 0
        my_count = board.count(self.ai_player)
        opp_count = board.count(self.opp_player)
        
        # 1. 駒の数（最重要）
        score += my_count * 100
        score -= opp_count * 100

        # 2. ミルの数
        for m in MILLS:
            if all(board[p] == self.ai_player for p in m): score += 35
            if all(board[p] == self.opp_player for p in m): score -= 35

        # 3. 移動の自由度（詰み防止・HARDでは重要視する）
        if phase == 2:
            for i, v in enumerate(board):
                if v == self.ai_player:
                    score += sum(1 for n in ADJACENCY[i] if board[n] == 0) * (8 if self.difficulty == "HARD" else 4)
                elif v == self.opp_player:
                    score -= sum(1 for n in ADJACENCY[i] if board[n] == 0) * (8 if self.difficulty == "HARD" else 4)
        return score

    def select_place(self, game):
        """フェーズ1: 配置手決定"""
        empty_indices = [i for i, v in enumerate(game.board) if v == 0]

        # EASYモード：30%の確率で完全ランダム
        if self.difficulty == "EASY" and random.random() < 0.3:
            return random.choice(empty_indices)

        # 1. 即ミル完成の手
        for idx in empty_indices:
            temp_board = list(game.board)
            temp_board[idx] = self.ai_player
            if any(all(temp_board[p] == self.ai_player for p in m) for m in MILLS if idx in m):
                return idx

        # 2. 相手のミル阻止（EASY以外）
        if self.difficulty != "EASY":
            for idx in empty_indices:
                temp_board = list(game.board)
                temp_board[idx] = self.opp_player
                if any(all(temp_board[p] == self.opp_player for p in m) for m in MILLS if idx in m):
                    return idx

        # 3. ベストスコアの探索
        best_score = -9999
        best_moves = []
        for idx in empty_indices:
            temp_board = list(game.board)
            temp_board[idx] = self.ai_player
            score = self.evaluate_board(temp_board, game.phase)
            if score > best_score:
                best_score = score
                best_moves = [idx]
            elif score == best_score:
                best_moves.append(idx)
        return random.choice(best_moves)

    def select_move(self, game):
        """フェーズ2: 移動手決定"""
        my_pieces = [i for i, v in enumerate(game.board) if v == self.ai_player]
        can_fly = game.board.count(self.ai_player) == 3
        
        legal_moves = []
        for start in my_pieces:
            targets = [i for i, v in enumerate(game.board) if v == 0] if can_fly else ADJACENCY[start]
            for target in targets:
                if game.board[target] == 0:
                    legal_moves.append((start, target))

        if not legal_moves: return None

        # EASYモード：30%でランダム
        if self.difficulty == "EASY" and random.random() < 0.3:
            return random.choice(legal_moves)

        # 1. 即ミル完成
        for start, target in legal_moves:
            temp_board = list(game.board)
            temp_board[start] = 0
            temp_board[target] = self.ai_player
            if any(all(temp_board[p] == self.ai_player for p in m) for m in MILLS if target in m):
                return start, target

        # 2. HARDモード：相手の次の手（1手先読み）をシミュレート
        if self.difficulty == "HARD":
            best_score = -9999
            best_moves = []
            for start, target in legal_moves:
                temp_board = list(game.board)
                temp_board[start] = 0
                temp_board[target] = self.ai_player
                
                # 簡易ミニマックス：この後相手が打つであろう最善手のスコアを引く
                opp_best_response = -999
                opp_pieces = [i for i, v in enumerate(temp_board) if v == self.opp_player]
                opp_can_fly = temp_board.count(self.opp_player) == 3
                
                for o_start in opp_pieces:
                    o_targets = [i for i, v in enumerate(temp_board) if v == 0] if opp_can_fly else ADJACENCY[o_start]
                    for o_target in o_targets:
                        if temp_board[o_target] == 0:
                            sim_board = list(temp_board)
                            sim_board[o_start] = 0
                            sim_board[o_target] = self.opp_player
                            # 相手目線の評価（AIにはマイナス）
                            opp_score = -self.evaluate_board(sim_board, game.phase)
                            if opp_score > opp_best_response:
                                opp_best_response = opp_score
                
                total_score = self.evaluate_board(temp_board, game.phase) - (opp_best_response if opp_best_response != -999 else 0)
                if total_score > best_score:
                    best_score = total_score
                    best_moves = [(start, target)]
                elif total_score == best_score:
                    best_moves.append((start, target))
            return random.choice(best_moves)

        # NORMAL / EASY(ランダムを引かなかった時)
        best_score = -9999
        best_moves = []
        for start, target in legal_moves:
            temp_board = list(game.board)
            temp_board[start] = 0
            temp_board[target] = self.ai_player
            score = self.evaluate_board(temp_board, game.phase)
            if score > best_score:
                best_score = score
                best_moves = [(start, target)]
            elif score == best_score:
                best_moves.append((start, target))
        return random.choice(best_moves)

    def select_remove(self, game, removable_indices):
        """ミル成立時：削除する駒の決定"""
        if self.difficulty != "EASY":
            for idx in removable_indices:
                for m in MILLS:
                    if idx in m:
                        if sum(1 for p in m if game.board[p] == self.opp_player) == 2:
                            return idx # 相手のリーチを最優先破壊
        return random.choice(removable_indices)


# --- メインゲームクラス ---
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Nine Men's Morris - Difficulty Deluxe")
        self.clock = pygame.time.Clock()
        
        # --- 🔲 豆腐文字対策：日本語フォントの選定ロジック ---
        self.font = None
        self.title_font = None
        
        # パターンA: 外部ファイル "NotoSansJP-Regular.ttf" からの直接読み込みを試みる
        try:
            self.font = pygame.font.Font("NotoSansJP-Regular.ttf", 28)
            self.title_font = pygame.font.Font("NotoSansJP-Regular.ttf", 48)
        except FileNotFoundError:
            # パターンB: ファイルが無い場合、PC内のシステム日本語フォントの自動検出
            font_candidates = [
                "notosanscjp", "notosanscjpnormal", "notosansjapanese",  # Noto Sans系
                "msgothic", "msmincho", "meiryo", "yu_gothic",          # Windows用
                "hiraginokakugothicpro", "hiraginosans", "osaka",       # Mac用
                "takao", "vlgothic"                                      # Linux用
            ]
            available_fonts = pygame.font.get_fonts()
            for f_name in font_candidates:
                if f_name in available_fonts:
                    self.font = pygame.font.SysFont(f_name, 28)
                    self.title_font = pygame.font.SysFont(f_name, 48)
                    break
            
            # パターンC: 上記の候補が全滅した場合のOS別OS標準フォールバック
            if self.font is None:
                if sys.platform == "win32":
                    self.font = pygame.font.SysFont("msgothic", 28)
                    self.title_font = pygame.font.SysFont("msgothic", 48)
                else:
                    self.font = pygame.font.SysFont("sans", 28)
                    self.title_font = pygame.font.SysFont("sans", 48)
        
        self.sounds = SoundManager()
        self.state = "TITLE" # TITLE, PLAYING
        self.difficulty = "NORMAL"
        
        # タイトル用ボタンエリア定義
        self.buttons = {
            "EASY": pygame.Rect(WIDTH//2 - 100, 300, 200, 50),
            "NORMAL": pygame.Rect(WIDTH//2 - 100, 380, 200, 50),
            "HARD": pygame.Rect(WIDTH//2 - 100, 460, 200, 50)
        }

    def init_game(self, difficulty):
        self.board = [0]*24
        self.turn = 1 # 1:人間(赤), 2:AI(青)
        self.phase = 1 
        self.pieces_to_place = [9, 9]
        self.removing_mode = False
        self.selected = None
        self.fades = []
        self.flash = None
        self.difficulty = difficulty
        self.message = f"難易度 [{difficulty}] で開始。あなたの番です"
        self.game_active = True
        self.ai = MorrisAI(difficulty=difficulty, ai_player=2)
        self.ai_delay_timer = 0
        self.state = "PLAYING"

    def is_mill(self, idx, player):
        return any(all(self.board[p] == player for p in m) for m in MILLS if idx in m)

    def get_removable(self, opponent):
        others = [i for i, v in enumerate(self.board) if v == opponent]
        non_mills = [i for i in others if not self.is_mill(i, opponent)]
        return non_mills if non_mills else others

    def has_legal_moves(self, player):
        if self.phase == 1: return True
        if self.board.count(player) == 3: return self.board.count(0) > 0
        for i, v in enumerate(self.board):
            if v == player:
                for neighbor in ADJACENCY[i]:
                    if self.board[neighbor] == 0: return True
        return False

    def handle_click(self, pos):
        if self.state == "TITLE":
            for diff, rect in self.buttons.items():
                if rect.collidepoint(pos):
                    self.init_game(diff)
                    return
            return

        if self.state == "PLAYING":
            if not self.game_active or self.turn == 2: return 
            for i, p_pos in enumerate(SCREEN_POS):
                if math.hypot(pos[0]-p_pos[0], pos[1]-p_pos[1]) < CIRCLE_RADIUS:
                    self.logic(i)
                    return
            if self.phase == 2 and not self.removing_mode:
                self.selected = None

    def logic(self, i):
        if self.removing_mode:
            opponent = 3 - self.turn
            if self.board[i] == opponent and i in self.get_removable(opponent):
                self.remove_piece(i, opponent)
            return

        if self.phase == 1:
            if self.board[i] == 0:
                self.board[i] = self.turn
                self.pieces_to_place[self.turn-1] -= 1
                self.sounds.play("place")
                if self.is_mill(i, self.turn): self.trigger_mill(i)
                else: self.next_turn()
            return

        elif self.phase == 2:
            if self.selected is None:
                if self.board[i] == self.turn: self.selected = i
            else:
                if self.board[i] == self.turn:
                    self.selected = i
                    return
                can_fly = self.board.count(self.turn) == 3
                if self.board[i] == 0 and (i in ADJACENCY[self.selected] or can_fly):
                    self.board[self.selected] = 0
                    self.board[i] = self.turn
                    self.selected = None
                    self.sounds.play("place")
                    if self.is_mill(i, self.turn): self.trigger_mill(i)
                    else: self.next_turn()
                else:
                    self.selected = None

    def remove_piece(self, i, opponent):
        self.fades.append(FadingPiece(SCREEN_POS[i], RED if opponent==1 else BLUE))
        self.board[i] = 0
        self.sounds.play("remove")
        self.removing_mode = False
        self.flash = None
        if self.check_win_condition(): return
        self.next_turn()

    def trigger_mill(self, i):
        self.removing_mode = True
        self.sounds.play("mill")
        m_list = [m for m in MILLS if i in m and all(self.board[p]==self.turn for p in m)]
        if m_list:
            self.flash = FlashingMill(m_list[0], RED if self.turn==1 else BLUE)
        if self.turn == 1:
            self.message = "ミル完成！相手の駒を取ってください"
        else:
            self.message = "AIがミルを完成させました！"

    def check_win_condition(self):
        opp = 3 - self.turn
        if sum(self.pieces_to_place) == 0 and self.board.count(opp) < 3:
            self.message = "ゲーム終了！ あなたの勝利！" if self.turn == 1 else "ゲーム終了！ AIの勝利！"
            self.game_active = False
            return True
        if sum(self.pieces_to_place) == 0 and not self.has_legal_moves(opp):
            self.message = "相手は移動できません。あなたの勝利！" if self.turn == 1 else "AIの勝利！"
            self.game_active = False
            return True
        return False

    def next_turn(self):
        if not self.game_active: return
        if sum(self.pieces_to_place) == 0: self.phase = 2
        self.turn = 3 - self.turn
        
        if self.phase == 2 and not self.has_legal_moves(self.turn):
            self.message = "移動不能です。AI的勝利！" if self.turn == 1 else "移動不能です。あなたの勝利！"
            self.game_active = False
            return

        if self.turn == 1:
            phase_str = "配置" if self.phase == 1 else ("フライング" if self.board.count(1) == 3 else "移動")
            self.message = f"あなたの番です ({phase_str})"
        else:
            self.message = "AI思考中..."
            self.ai_delay_timer = pygame.time.get_ticks()

    def update_game(self):
        if self.state != "PLAYING": return
        if self.flash and self.flash.active: self.flash.update()
        for f in self.fades[:]:
            f.update()
            if not f.active: self.fades.remove(f)

        if self.game_active and self.turn == 2:
            current_time = pygame.time.get_ticks()
            if current_time - self.ai_delay_timer > 600: # 0.6秒待機
                self.run_ai_logic()

    def run_ai_logic(self):
        if self.removing_mode:
            removable = self.get_removable(opponent=1)
            target = self.ai.select_remove(self, removable)
            self.remove_piece(target, opponent=1)
            return

        if self.phase == 1:
            target_idx = self.ai.select_place(self)
            self.logic(target_idx)
        elif self.phase == 2:
            move = self.ai.select_move(self)
            if move:
                start, target = move
                self.selected = start
                self.logic(target)

    def draw_title(self):
        self.screen.fill(BEIGE)
        title_surf = self.title_font.render("Nine Men's Morris", True, BLACK)
        self.screen.blit(title_surf, (WIDTH//2 - title_surf.get_width()//2, 120))
        
        sub_surf = self.font.render("Select Difficulty", True, BLACK)
        self.screen.blit(sub_surf, (WIDTH//2 - sub_surf.get_width()//2, 220))

        # ボタンの描画
        colors = {"EASY": (100, 200, 100), "NORMAL": (100, 150, 220), "HARD": (220, 100, 100)}
        for diff, rect in self.buttons.items():
            pygame.draw.rect(self.screen, colors[diff], rect, border_radius=8)
            pygame.draw.rect(self.screen, BLACK, rect, 2, border_radius=8)
            txt = self.font.render(diff, True, WHITE)
            self.screen.blit(txt, (rect.centerx - txt.get_width()//2, rect.centery - txt.get_height()//2))

    def draw_game(self):
        self.screen.fill(BEIGE)
        for i in range(3):
            s = i*BOARD_SIZE//6 + OFFSET
            size = BOARD_SIZE - i*BOARD_SIZE//3
            pygame.draw.rect(self.screen, BLACK, (s, s, size, size), 3)
        mid = WIDTH//2
        lines = [((OFFSET,mid),(OFFSET+BOARD_SIZE//3,mid)), ((WIDTH-OFFSET-BOARD_SIZE//3,mid),(WIDTH-OFFSET,mid)),
                 ((mid,OFFSET),(mid,OFFSET+BOARD_SIZE//3)), ((mid,WIDTH-OFFSET-BOARD_SIZE//3),(mid,WIDTH-OFFSET))]
        for l in lines: pygame.draw.line(self.screen, BLACK, l[0], l[1], 3)

        for i, v in enumerate(self.board):
            color = RED if v==1 else BLUE if v==2 else (180,180,180)
            if v != 0:
                pygame.draw.circle(self.screen, BLACK, SCREEN_POS[i], CIRCLE_RADIUS+2)
                pygame.draw.circle(self.screen, color, SCREEN_POS[i], CIRCLE_RADIUS)
            else:
                pygame.draw.circle(self.screen, color, SCREEN_POS[i], 6)

        if self.selected is not None:
            pygame.draw.circle(self.screen, YELLOW, SCREEN_POS[self.selected], CIRCLE_RADIUS+6, 4)

        if self.flash and self.flash.active: self.flash.draw(self.screen)
        for f in self.fades: f.draw(self.screen)

        msg_surf = self.font.render(self.message, True, BLACK)
        self.screen.blit(msg_surf, (WIDTH//2 - msg_surf.get_width()//2, 30))

    def draw(self):
        if self.state == "TITLE": self.draw_title()
        elif self.state == "PLAYING": self.draw_game()
        pygame.display.flip()

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN: self.handle_click(e.pos)
            
            self.update_game()
            self.draw()
            self.clock.tick(FPS)

if __name__ == "__main__":
    Game().run()
