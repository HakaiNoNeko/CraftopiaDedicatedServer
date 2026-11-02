import sqlite3, tarfile, tempfile, unittest
from pathlib import Path
import craftopia_server as cs


def make_mgr(tmp):
    cfg = cs.load_config(Path(tmp) / "config.json")
    cfg.update(install_dir=str(tmp), data_dir=str(Path(tmp) / "data"))
    m = cs.Manager(cfg)
    m.sent = []
    m.send = m.sent.append
    return m


class Tests(unittest.TestCase):
    def test_backup_snapshots_db_and_prunes(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            t = Path(t); save = t / "save"; (save / "Worlds").mkdir(parents=True)
            db = sqlite3.connect(save / "Worlds" / "w.db"); db.execute("create table x(a)"); db.execute("insert into x values (7)"); db.commit(); db.close()
            for _ in range(3):
                out = cs.make_backup(save, t / "bk", keep=2)
                (t / "bk" / "craftopia-0.tar.gz").touch()  # ensure distinct sort keys
            self.assertEqual(len(list((t / "bk").glob("craftopia-*.tar.gz"))), 2)
            self.assertIn("save/Worlds/w.db", tarfile.open(out).getnames())

    def test_permissions_and_stores(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            m = make_mgr(t)
            self.assertEqual(m.run_command("kick bob", admin=False), "Admins only.")
            m.run_command("admin add Alice"); self.assertTrue(m.admins.has("alice"))
            m.run_command("whitelist add Bob"); m.run_command("whitelist on")
            self.assertTrue(m.cfg["whitelist_enabled"])
            m.run_command("whitelist remove bob"); self.assertFalse(m.whitelist.has("Bob"))

    def test_whitelist_and_ban_kick(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            m = make_mgr(t); m.cfg["whitelist_enabled"] = True; m.admins.add("Alice"); m.whitelist.add("Bob")
            m.player_re = __import__("re").compile(m.cfg["player_regex"])
            lines = ["playerId,name", '1,"Alice"', '2,"Bob"', '3,"Eve"', '4,""']
            m.send = lambda c: (m.sent.append(c), c == "list" and [m.on_line(l) for l in lines])
            m.poll_players()
            self.assertEqual([c for c in m.sent if c.startswith("kick")], ["kick 3"])
            m.bans.add("Bob"); m.poll_players()
            self.assertIn("kick 2", m.sent)

    def test_chat_command_routing(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            m = make_mgr(t); m.admins.add("Alice"); m.players = {"5": "Eve"}
            m.chat_command("Eve", "!kick Eve"); self.assertNotIn("kick 5", m.sent)
            m.chat_command("Alice", "!kick Eve"); self.assertIn("kick 5", m.sent)
            m.players["7"] = "Alice"; m.sent.clear()
            m.on_line("[Chat] 7: !kick Eve"); __import__("time").sleep(0.3)  # id 7 resolves to admin Alice
            self.assertIn("kick 5", m.sent)

    def test_config_gets_token_when_installer_omits_it(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            p = Path(t) / "sub" / "config.json"; p.parent.mkdir(); p.write_text('{"install_dir": "X"}')
            cfg = cs.load_config(p)
            self.assertEqual(len(cfg["api"]["token"]), 32)
            self.assertEqual(cs.load_config(p)["api"]["token"], cfg["api"]["token"])  # persisted, stable


if __name__ == "__main__":
    unittest.main()
