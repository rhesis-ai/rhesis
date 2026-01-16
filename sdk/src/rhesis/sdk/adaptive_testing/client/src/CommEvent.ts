
// The base class for all communication data over websocket
export class CommEvent {
  // Using snake case because these objects will be parsed in Python backend
  readonly event_id: string;
  constructor(event_id: string, data?: object) {
    this.event_id = event_id;
    if (data) {
      for (const k of Object.keys(data)) {
        this[k] = data[k];
      }
    }
  }
}


export function finishTopicDescription(topic_marker_id: string, description: string) {
  return new CommEvent("change_description", {"topic_marker_id": topic_marker_id, "description": description});
}


export function redraw() {
  return new CommEvent("redraw");
}


export function generateSuggestions(data: object) {
  return new CommEvent("generate_suggestions", data);
}


export function clearSuggestions() {
  return new CommEvent("clear_suggestions")
}


export function setFirstModel(model: string) {
  return new CommEvent("set_first_model", { "model": model });
}


export function changeGenerator(generator: string) {
  return new CommEvent("change_generator", { "generator": generator });
}


export function changeMode(mode: string) {
  return new CommEvent("change_mode", {"mode": mode})
}


export function addTopic() {
  return new CommEvent("add_new_topic")
}


export function addTest() {
  return new CommEvent("add_new_test");
}


export function changeFilter(filter_text: string) {
  return new CommEvent("change_filter", {"filter_text": filter_text});
}


export function changeTopic(topic: string) {
  return new CommEvent("change_topic", {"topic": topic});
}


export function moveTest(test_ids: string[] | string, topic: string) {
  if (!Array.isArray(test_ids)) {
    test_ids = [test_ids]
  }
  return new CommEvent("move_test", { "test_ids": test_ids, "topic": topic });
}


export function deleteTest(test_ids: string[] | string) {
  if (!Array.isArray(test_ids)) {
    test_ids = [test_ids]
  }
  return new CommEvent("delete_test", { "test_ids": test_ids });
}


export function changeLabel(test_id: string, label: string, labeler: string) {
  return new CommEvent("change_label", { "test_ids": [test_id], "label": label, "labeler": labeler });
}


export function changeInput(test_id: string, input: string) {
  return new CommEvent("change_input", { "test_ids": [test_id], "input": input });
}


export function changeOutput(test_id: string, output: string) {
  return new CommEvent("change_output", { "test_ids": [test_id], "output": output });
}
