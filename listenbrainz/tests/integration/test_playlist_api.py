from uuid import UUID

from redis import Redis
from flask import url_for, current_app
from listenbrainz.tests.integration import IntegrationTestCase
import listenbrainz.db.user as db_user
from listenbrainz.webserver.views.playlist_api import PLAYLIST_TRACK_URI_PREFIX, PLAYLIST_URI_PREFIX
import ujson


def get_test_data():
    return {
       "playlist": {
          "title": "1980s flashback jams",
          "track": [
             {
                "identifier": "https://musicbrainz.org/recording/e8f9b188-f819-4e43-ab0f-4bd26ce9ff56"
             }
          ],
       }
    }


class PlaylistAPITestCase(IntegrationTestCase):
    """
        Base class to properly setup our test environment.
    """

    def setUp(self):
        super(PlaylistAPITestCase, self).setUp()
        self.user = db_user.get_or_create(1, "testuserpleaseignore")
        self.user2 = db_user.get_or_create(2, "anothertestuserpleaseignore")
        self.user3 = db_user.get_or_create(3, "troi-bot")

    def tearDown(self):
        r = Redis(host=current_app.config['REDIS_HOST'], port=current_app.config['REDIS_PORT'])
        r.flushall()
        super(PlaylistAPITestCase, self).tearDown()

    def test_playlist_create_and_get(self):
        """ Test to ensure creating a playlist works """

        playlist = get_test_data()

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist", public="true"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        self.assertEqual(response.json["status"], "ok")
        self.assertNotEqual(response.json["playlist_mbid"], "")

        playlist_mbid = response.json["playlist_mbid"]

        # Make sure the return playlist id is valid
        UUID(response.json["playlist_mbid"])

        # Test to ensure fetching a playlist works
        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])}
        )
        self.assert200(response)
        self.assertEqual(response.json["playlist"]["creator"], "testuserpleaseignore")
        self.assertEqual(response.json["playlist"]["identifier"], PLAYLIST_URI_PREFIX + playlist_mbid)
        self.assertEqual(response.json["playlist"]["track"][0]["identifier"],
                         playlist["playlist"]["track"][0]["identifier"])

    def test_playlist_create_with_created_for(self):
        """ Test to ensure creating a playlist for someone else works """

        # Submit a playlist on a different user's behalf
        playlist = get_test_data()
        playlist["playlist"]["created_for"] = self.user["musicbrainz_id"]

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist", public="true"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user3["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        playlist_mbid = response.json["playlist_mbid"]

        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])}
        )
        self.assert200(response)
        self.assertEqual(response.json["playlist"]["created_for"], self.user["musicbrainz_id"])

        # Try to submit a playlist on a different users's behalf without the right perms
        response = self.client.post(
            url_for("playlist_api_v1.create_playlist", public="true"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert403(response)

    def test_playlist_get_non_existent(self):
        """ Test to ensure fetching a non existent playlist gives 404 """

        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid="0ebcde36-1b14-4be5-ad3e-a088caf69134"),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])}
        )
        self.assert404(response)

    def test_playlist_create_and_get_private(self):
        """ Test to ensure creating a private playlist works """

        playlist = get_test_data()

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist", public="false"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        self.assertEqual(response.json["status"], "ok")
        self.assertNotEqual(response.json["playlist_mbid"], "")

        playlist_mbid = response.json["playlist_mbid"]

        # Test to ensure fetching a private playlist from a non-owner fails with 404
        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])}
        )
        self.assert404(response)

    def test_playlist_create_empty(self):
        """ Test to ensure creating an empty playlist works """

        playlist = {
           "playlist": {
              "title": "yer dreams suck!"
           }
        }

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        self.assertEqual(response.json["status"], "ok")
        self.assertNotEqual(response.json["playlist_mbid"], "")

        # Make sure the return playlist id is valid
        UUID(response.json["playlist_mbid"])

    def test_playlist_json_with_missing_keys(self):
        """ Test for checking that submitting JSON with missing keys returns 400 """

        # submit a playlist without title
        playlist = {
           "playlist": {
              "track": [
                 {
                    "identifier": "https://musicbrainz.org/recording/e8f9b188-f819-4e43-ab0f-4bd26ce9ff56"
                 }
              ],
           }
        }

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert400(response)
        self.assertEqual(response.json["error"], "JSPF playlist must contain a title element with the title of the playlist.")

    def test_playlist_recording_add(self):
        """ Test adding a recording to a playlist works """

        playlist = get_test_data()

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        playlist_mbid = response.json["playlist_mbid"]

        # Add a track to the playlist
        add_recording = {
           "playlist": {
              "track": [
                 {
                    "identifier": PLAYLIST_TRACK_URI_PREFIX + "4a77a078-e91a-4522-a409-3b58aa7de3ae"
                 }
              ],
           }
        }
        response = self.client.post(
            url_for("playlist_api_v1.add_playlist_item", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            data=ujson.dumps(add_recording),
            content_type="application/json"
        )
        self.assert200(response)

        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])}
        )
        self.assertEqual(response.json["playlist"]["creator"], "testuserpleaseignore")
        self.assertEqual(response.json["playlist"]["identifier"], PLAYLIST_URI_PREFIX + playlist_mbid)
        self.assertEqual(response.json["playlist"]["track"][0]["identifier"],
                         playlist["playlist"]["track"][0]["identifier"])
        self.assertEqual(response.json["playlist"]["track"][1]["identifier"],
                         add_recording["playlist"]["track"][0]["identifier"])

        # Add an invalid track id to the playlist
        add_recording = {
           "playlist": {
              "track": [
                 {
                    "identifier": "4a77a078-e91a-4522-a409-3b58aa7de3ae"
                 }
              ],
           }
        }
        response = self.client.post(
            url_for("playlist_api_v1.add_playlist_item", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            data=ujson.dumps(add_recording),
            content_type="application/json"
        )
        self.assert400(response)

    def test_playlist_recording_move(self):

        playlist = {
           "playlist": {
              "title": "1980s flashback jams",
              "track": [
                 {
                    "identifier": PLAYLIST_TRACK_URI_PREFIX + "e8f9b188-f819-4e43-ab0f-4bd26ce9ff56"
                 },
                 {
                    "identifier": PLAYLIST_TRACK_URI_PREFIX + "57ef4803-5181-4b3d-8dd6-8b9d9ca83e2a"
                 }
              ],
           }
        }

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        playlist_mbid = response.json["playlist_mbid"]

        move = {"mbid": "57ef4803-5181-4b3d-8dd6-8b9d9ca83e2a", "from": 1, "to": 0, "count": 1}
        response = self.client.post(
            url_for("playlist_api_v1.move_playlist_item", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            data=ujson.dumps(move),
            content_type="application/json"
        )
        self.assert200(response)

        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])}
        )
        self.assertEqual(response.json["playlist"]["creator"], "testuserpleaseignore")
        self.assertEqual(response.json["playlist"]["identifier"], PLAYLIST_URI_PREFIX + playlist_mbid)
        self.assertEqual(response.json["playlist"]["track"][0]["identifier"],
                         playlist["playlist"]["track"][1]["identifier"])
        self.assertEqual(response.json["playlist"]["track"][1]["identifier"],
                         playlist["playlist"]["track"][0]["identifier"])

    def test_playlist_recording_delete(self):

        playlist = {
           "playlist": {
              "title": "1980s flashback jams",
              "track": [
                 {
                    "identifier": "https://musicbrainz.org/recording/e8f9b188-f819-4e43-ab0f-4bd26ce9ff56"
                 },
                 {
                    "identifier": "https://musicbrainz.org/recording/57ef4803-5181-4b3d-8dd6-8b9d9ca83e2a"
                 }
              ],
           }
        }

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        playlist_mbid = response.json["playlist_mbid"]

        move = {"index": 0, "count": 1}
        response = self.client.post(
            url_for("playlist_api_v1.delete_playlist_item", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            data=ujson.dumps(move),
            content_type="application/json"
        )
        self.assert200(response)

        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])}
        )
        self.assertEqual(response.json["playlist"]["creator"], "testuserpleaseignore")
        self.assertEqual(response.json["playlist"]["identifier"], PLAYLIST_URI_PREFIX + playlist_mbid)
        self.assertEqual(response.json["playlist"]["track"][0]["identifier"],
                         playlist["playlist"]["track"][1]["identifier"])

    def test_playlist_delete_playlist(self):

        playlist = {
           "playlist": {
              "title": "yer dreams suck!"
           }
        }

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        playlist_mbid = response.json["playlist_mbid"]

        response = self.client.post(
            url_for("playlist_api_v1.delete_playlist", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)

        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert404(response)

    def test_playlist_copy_public_playlist(self):

        playlist = {
           "playlist": {
              "title": "my stupid playlist"
           }
        }

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist", public="true"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        playlist_mbid = response.json["playlist_mbid"]

        response = self.client.post(
            url_for("playlist_api_v1.copy_playlist", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        new_playlist_mbid = response.json["playlist_mbid"]
        self.assertNotEqual(playlist_mbid, new_playlist_mbid)

        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid=new_playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        self.assertEqual(response.json["playlist"]["identifier"], PLAYLIST_URI_PREFIX + new_playlist_mbid)
        self.assertEqual(response.json["playlist"]["extension"]["https://musicbrainz.org/doc/jspf#playlist"]["public"], "true")
        self.assertEqual(response.json["playlist"]["title"], "Copy of my stupid playlist")
        self.assertEqual(response.json["playlist"]["creator"], "anothertestuserpleaseignore")

    def test_playlist_copy_private_playlist(self):

        playlist = {
           "playlist": {
              "title": "my stupid playlist"
           }
        }

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist", public="false"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        playlist_mbid = response.json["playlist_mbid"]

        response = self.client.post(
            url_for("playlist_api_v1.copy_playlist", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        new_playlist_mbid = response.json["playlist_mbid"]

        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid=new_playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        self.assertEqual(response.json["playlist"]["extension"]["https://musicbrainz.org/doc/jspf#playlist"]["public"], "false")
        self.assertEqual(response.json["playlist"]["title"], "Copy of my stupid playlist")
        self.assertEqual(response.json["playlist"]["creator"], "testuserpleaseignore")

    def test_playlist_private_access(self):
        """ Test for checking that unauthorized access to private playlists return 404 """

        # create a private playlist, then try to access it from the wrong user for all the endpoints
        playlist = get_test_data()
        response = self.client.post(
            url_for("playlist_api_v1.create_playlist", public="false"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        playlist_mbid = response.json["playlist_mbid"]

        response = self.client.get(
            url_for("playlist_api_v1.get_playlist", playlist_mbid=playlist_mbid),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
        )
        self.assert404(response)

        # Add recording to playlist
        response = self.client.post(
            url_for("playlist_api_v1.add_playlist_item", offset=0, playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
            content_type="application/json"
        )
        self.assert404(response)

        # Move recording in playlist
        response = self.client.post(
            url_for("playlist_api_v1.move_playlist_item", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
            content_type="application/json"
        )
        self.assert404(response)

        # Delete recording in playlist
        response = self.client.post(
            url_for("playlist_api_v1.delete_playlist_item", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
            content_type="application/json"
        )
        self.assert404(response)

        # Delete a playlist
        response = self.client.post(
            url_for("playlist_api_v1.delete_playlist", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
            content_type="application/json"
        )
        self.assert404(response)

        # Copy a playlist
        response = self.client.post(
            url_for("playlist_api_v1.copy_playlist", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
            content_type="application/json"
        )
        self.assert404(response)

    def test_playlist_unauthorized_access(self):
        """ Test for checking that unauthorized access return 401 """

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist", public="false"),
            data=ujson.dumps({}),
            content_type="application/json"
        )
        self.assert401(response)

        playlist_mbid = "d1ff6a3d-f471-416f-94e7-86778b51fa2b"
        # Add recording to playlist
        response = self.client.post(
            url_for("playlist_api_v1.add_playlist_item", offset=0, playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            content_type="application/json"
        )
        self.assert401(response)

        # Move recording in playlist
        response = self.client.post(
            url_for("playlist_api_v1.move_playlist_item", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            content_type="application/json"
        )
        self.assert401(response)

        # Delete recording in playlist
        response = self.client.post(
            url_for("playlist_api_v1.delete_playlist_item", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            content_type="application/json"
        )
        self.assert401(response)

        # Delete a playlist
        response = self.client.post(
            url_for("playlist_api_v1.delete_playlist", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            content_type="application/json"
        )
        self.assert401(response)

        # Copy a playlist
        response = self.client.post(
            url_for("playlist_api_v1.copy_playlist", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            content_type="application/json"
        )
        self.assert401(response)

    def test_playlist_invalid_user(self):
        """ Test for checking that forbidden access returns 403 """

        playlist = {
           "playlist": {
              "title": "my stupid playlist"
           }
        }

        response = self.client.post(
            url_for("playlist_api_v1.create_playlist", public="true"),
            data=ujson.dumps(playlist),
            headers={"Authorization": "Token {}".format(self.user["auth_token"])},
            content_type="application/json"
        )
        self.assert200(response)
        playlist_mbid = response.json["playlist_mbid"]

        # Add recording to playlist
        response = self.client.post(
            url_for("playlist_api_v1.add_playlist_item", offset=0, playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
            content_type="application/json"
        )
        self.assert403(response)

        # Move recording in playlist
        response = self.client.post(
            url_for("playlist_api_v1.move_playlist_item", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
            content_type="application/json"
        )
        self.assert403(response)

        # Delete recording in playlist
        response = self.client.post(
            url_for("playlist_api_v1.delete_playlist_item", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
            content_type="application/json"
        )
        self.assert403(response)

        # Delete a playlist
        response = self.client.post(
            url_for("playlist_api_v1.delete_playlist", playlist_mbid=playlist_mbid),
            data=ujson.dumps({}),
            headers={"Authorization": "Token {}".format(self.user2["auth_token"])},
            content_type="application/json"
        )
        self.assert403(response)
