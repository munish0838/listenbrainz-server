import * as React from "react";
import { mount, ReactWrapper, shallow } from "enzyme";

import { act } from "react-dom/test-utils";
import PinnedRecordingCard, {
  PinnedRecordingCardProps,
  PinnedRecordingCardState,
} from "../../src/pins/PinnedRecordingCard";
import * as utils from "../../src/utils/utils";
import APIServiceClass from "../../src/utils/APIService";
import GlobalAppContext, {
  GlobalAppContextT,
} from "../../src/utils/GlobalAppContext";
import { waitForComponentToPaint } from "../test-utils";
import RecordingFeedbackManager from "../../src/utils/RecordingFeedbackManager";
import ListenCard from "../../src/listens/ListenCard";

// Font Awesome generates a random hash ID for each icon everytime.
// Mocking Math.random() fixes this
// https://github.com/FortAwesome/react-fontawesome/issues/194#issuecomment-627235075
jest.spyOn(global.Math, "random").mockImplementation(() => 0);

const user = {
  id: 1,
  name: "name",
  auth_token: "auth_token",
};

const globalProps: GlobalAppContextT = {
  APIService: new APIServiceClass(""),
  websocketsUrl: "",
  currentUser: user,
  spotifyAuth: {},
  youtubeAuth: {},
  recordingFeedbackManager: new RecordingFeedbackManager(
    new APIServiceClass("foo"),
    { name: "Fnord" }
  ),
};

const pinnedRecording: PinnedRecording = {
  blurb_content: "I LOVE",
  created: 1111111111,
  pinned_until: 9999999999,
  row_id: 1,
  recording_mbid: "98255a8c-017a-4bc7-8dd6-1fa36124572b",
  track_metadata: {
    artist_name: "Rick Astley",
    track_name: "Never Gonna Give You Up",
  },
};

const expiredPinnedRecording: PinnedRecording = {
  ...pinnedRecording,
  pinned_until: 1111122222,
};

const props: PinnedRecordingCardProps = {
  pinnedRecording,
  isCurrentUser: true,

  removePinFromPinsList: () => {},
};

describe("PinnedRecordingCard", () => {
  it("renders correctly", () => {
    const wrapper = mount<PinnedRecordingCard>(
      <PinnedRecordingCard {...props} />
    );
    expect(wrapper.find(ListenCard)).toHaveLength(1);
  });

  describe("determineIfCurrentlyPinned", () => {
    it("returns true when pinned_until > now", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <PinnedRecordingCard {...props} />
      );
      const instance = wrapper.instance();

      let isPlaying;
      await act(() => {
        isPlaying = instance.determineIfCurrentlyPinned();
      });
      expect(isPlaying).toBe(true);
    });

    it("returns false when pinned_until < now", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <PinnedRecordingCard
          {...{ ...props, pinnedRecording: expiredPinnedRecording }}
        />
      );
      const instance = wrapper.instance();
      let isPlaying;
      await act(() => {
        isPlaying = instance.determineIfCurrentlyPinned();
      });
      expect(isPlaying).toBe(false);
    });
  });

  describe("unpinRecording", () => {
    it("calls API, updates currentlyPinned in state", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <GlobalAppContext.Provider value={globalProps}>
          <PinnedRecordingCard {...props} />
        </GlobalAppContext.Provider>
      );
      const instance = wrapper.instance();

      const { APIService } = instance.context;
      const spy = jest.spyOn(APIService, "unpinRecording");
      spy.mockImplementation(() => Promise.resolve(200));

      expect(wrapper.state("currentlyPinned")).toBeTruthy();

      await act(async () => {
        await instance.unpinRecording();
      });
      await waitForComponentToPaint(wrapper);

      expect(spy).toHaveBeenCalledTimes(1);
      expect(spy).toHaveBeenCalledWith("auth_token");

      expect(wrapper.state("currentlyPinned")).toBeFalsy();
    });

    it("does nothing if isCurrentUser is false", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <GlobalAppContext.Provider value={globalProps}>
          <PinnedRecordingCard {...{ ...props, isCurrentUser: false }} />
        </GlobalAppContext.Provider>
      );
      const instance = wrapper.instance();

      const { APIService } = instance.context;
      const spy = jest.spyOn(APIService, "unpinRecording");
      spy.mockImplementation(() => Promise.resolve(200));

      expect(wrapper.state("currentlyPinned")).toBeTruthy();
      await act(async () => {
        await instance.unpinRecording();
      });
      await waitForComponentToPaint(wrapper);

      expect(spy).toHaveBeenCalledTimes(0);
      expect(wrapper.state("currentlyPinned")).toBeTruthy();
    });

    it("does nothing if CurrentUser.authtoken is not set", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <GlobalAppContext.Provider
          value={{
            ...globalProps,
            currentUser: { auth_token: undefined, name: "test" },
          }}
        >
          <PinnedRecordingCard {...props} />
        </GlobalAppContext.Provider>
      );
      const instance = wrapper.instance();

      const { APIService } = instance.context;
      const spy = jest.spyOn(APIService, "unpinRecording");
      spy.mockImplementation(() => Promise.resolve(200));

      expect(wrapper.state("currentlyPinned")).toBeTruthy();
      await act(async () => {
        await instance.unpinRecording();
      });
      await waitForComponentToPaint(wrapper);

      expect(spy).toHaveBeenCalledTimes(0);
      expect(wrapper.state("currentlyPinned")).toBeTruthy();
    });

    it("doesn't update currentlyPinned in state if status code is not 200", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <GlobalAppContext.Provider value={globalProps}>
          <PinnedRecordingCard {...{ ...props }} />
        </GlobalAppContext.Provider>
      );
      const instance = wrapper.instance();

      const { APIService } = instance.context;
      const spy = jest.spyOn(APIService, "unpinRecording");
      spy.mockImplementation(() => Promise.resolve(201));

      expect(wrapper.state("currentlyPinned")).toBeTruthy();
      await act(async () => {
        await instance.unpinRecording();
      });
      await waitForComponentToPaint(wrapper);

      expect(spy).toHaveBeenCalled();
      expect(wrapper.state("currentlyPinned")).toBeTruthy();
    });

    it("calls handleError if error is returned", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <GlobalAppContext.Provider value={globalProps}>
          <PinnedRecordingCard {...{ ...props }} />
        </GlobalAppContext.Provider>
      );
      const instance = wrapper.instance();
      instance.handleError = jest.fn();

      const error = new Error("error");
      const { APIService } = instance.context;
      const spy = jest.spyOn(APIService, "unpinRecording");
      spy.mockImplementation(() => {
        throw error;
      });

      await act(async () => {
        await instance.unpinRecording();
      });
      await waitForComponentToPaint(wrapper);
      expect(instance.handleError).toHaveBeenCalledTimes(1);
      expect(instance.handleError).toHaveBeenCalledWith(
        error,
        "Error while unpinning track"
      );
    });
  });

  describe("deletePin", () => {
    it("calls API and updates isDeleted and currentlyPinned in state", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <GlobalAppContext.Provider value={globalProps}>
          <PinnedRecordingCard {...{ ...props }} />
        </GlobalAppContext.Provider>
      );
      const instance = wrapper.instance();

      const { APIService } = instance.context;
      const spy = jest.spyOn(APIService, "deletePin");
      spy.mockImplementation(() => Promise.resolve(200));

      expect(wrapper.state("isDeleted")).toBeFalsy();
      expect(wrapper.state("currentlyPinned")).toBeTruthy();

      await act(async () => {
        await instance.deletePin(pinnedRecording);
      });
      await waitForComponentToPaint(wrapper);

      expect(spy).toHaveBeenCalledTimes(1);
      expect(spy).toHaveBeenCalledWith("auth_token", pinnedRecording.row_id);

      expect(wrapper.state("isDeleted")).toBeTruthy();
      expect(wrapper.state("currentlyPinned")).toBeFalsy();

      setTimeout(() => {
        expect(instance.props.removePinFromPinsList).toHaveBeenCalledTimes(1);
        expect(instance.props.removePinFromPinsList).toHaveBeenCalledWith(
          instance.props.pinnedRecording
        );
      }, 1000);
    });

    it("does nothing if isCurrentUser is false", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <GlobalAppContext.Provider value={globalProps}>
          <PinnedRecordingCard {...{ ...props, isCurrentUser: false }} />
        </GlobalAppContext.Provider>
      );
      const instance = wrapper.instance();

      const { APIService } = instance.context;
      const spy = jest.spyOn(APIService, "deletePin");
      spy.mockImplementation(() => Promise.resolve(200));

      expect(wrapper.state("isDeleted")).toBeFalsy();
      await act(async () => {
        await instance.deletePin(pinnedRecording);
      });
      await waitForComponentToPaint(wrapper);

      expect(spy).toHaveBeenCalledTimes(0);
      expect(wrapper.state("isDeleted")).toBeFalsy();
    });

    it("does nothing if CurrentUser.authtoken is not set", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <GlobalAppContext.Provider
          value={{
            ...globalProps,
            currentUser: { auth_token: undefined, name: "test" },
          }}
        >
          <PinnedRecordingCard {...props} />
        </GlobalAppContext.Provider>
      );
      const instance = wrapper.instance();

      const { APIService } = instance.context;
      const spy = jest.spyOn(APIService, "deletePin");
      spy.mockImplementation(() => Promise.resolve(200));

      expect(wrapper.state("isDeleted")).toBeFalsy();
      await act(async () => {
        await instance.deletePin(pinnedRecording);
      });
      await waitForComponentToPaint(wrapper);

      expect(spy).toHaveBeenCalledTimes(0);
      expect(wrapper.state("isDeleted")).toBeFalsy();
    });

    it("doesn't update currentlyPinned in state if status code is not 200", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <GlobalAppContext.Provider value={globalProps}>
          <PinnedRecordingCard {...{ ...props }} />
        </GlobalAppContext.Provider>
      );
      const instance = wrapper.instance();

      const { APIService } = instance.context;
      const spy = jest.spyOn(APIService, "deletePin");
      spy.mockImplementation(() => Promise.resolve(201));

      expect(wrapper.state("isDeleted")).toBeFalsy();
      await act(async () => {
        await instance.deletePin(pinnedRecording);
      });
      await waitForComponentToPaint(wrapper);

      expect(spy).toHaveBeenCalled();
      expect(wrapper.state("isDeleted")).toBeFalsy();
    });

    it("calls handleError if error is returned", async () => {
      const wrapper = mount<PinnedRecordingCard>(
        <GlobalAppContext.Provider value={globalProps}>
          <PinnedRecordingCard {...{ ...props }} />
        </GlobalAppContext.Provider>
      );
      const instance = wrapper.instance();
      instance.handleError = jest.fn();

      const error = new Error("error");
      const { APIService } = instance.context;
      const spy = jest.spyOn(APIService, "deletePin");
      spy.mockImplementation(() => {
        throw error;
      });

      await act(async () => {
        await instance.deletePin(pinnedRecording);
      });
      await waitForComponentToPaint(wrapper);
      expect(instance.handleError).toHaveBeenCalledTimes(1);
      expect(instance.handleError).toHaveBeenCalledWith(
        error,
        "Error while deleting pin"
      );
    });
  });
});
