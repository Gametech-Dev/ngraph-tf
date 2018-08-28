import tensorflow as tf
import argparse
import numpy as np
import ngraph
import json
import os


def calculate_output(frozen_graph_filename, select_device, input_example, input_tensor_name, output_tensor_name):
    """Calculate the output of the imported frozen graph given the input.

    Load the graph def from frozen_graph_file on selected device, then get the tensors based on the input and output name from the graph,
    then feed the input_example to the graph and retrieves the output vector.

    Args:
    frozen_graph_filename: The location of the frozen graph file. 
    select_device: "NGRAPH" or "CPU".
        input_example: Random generated input or actual image.
        input_tensor_name: Input tensor name in the frozen graph. 
        output_tensor_name: Output tensor name in the frozen graph.

    Returns:
        The output vector obtained from running the input_example through the graph.
    """

    with tf.gfile.GFile(frozen_graph_filename, "rb") as f:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(f.read())

    with tf.Graph().as_default() as graph:
        with tf.device('/job:localhost/replica:0/task:0/device:' + select_device + ':0'):
            tf.import_graph_def(graph_def)

    input_placeholder = graph.get_tensor_by_name(input_tensor_name)
    output_tensor = graph.get_tensor_by_name(output_tensor_name)

    config = tf.ConfigProto(
        allow_soft_placement=True,
        #log_device_placement=True,
        inter_op_parallelism_threads=1
    )

    with tf.Session(graph=graph, config=config) as sess:
        output_tensor = sess.run(output_tensor, feed_dict={
                                 input_placeholder: input_example})
        return output_tensor


def calculate_norm(ngraph_output, tf_output, desired_norm):
    """Calculate desired_norm between vectors.

    Calculate the L1/L2/inf norm between the NGRAPH and tensorflow output vectors.

    Args:
        ngraph_output: The output vector generated from NGRAPH graph.
        tf_output: The output vector generated from tensorflow graph.
        desired_norm: L1/L2/inf norm. 

    Returns:
        Calcualted norm between the vectors.

    Raises:
        Exception: If the dimension of the two vectors mismatch.
    """
    if(ngraph_output.shape != tf_output.shape):
        raise Exception('ngraph output and tf output dimension mismatch')

    ngraph_output_squeezed = np.squeeze(ngraph_output)
    tf_output_squeezed = np.squeeze(tf_output)

    ngraph_output_flatten = ngraph_output_squeezed.flatten()
    tf_output_flatten = tf_output_squeezed.flatten()

    factor = np.prod(ngraph_output_squeezed.shape)

    if desired_norm == 'l1_norm':
        return np.sum(np.abs(ngraph_output_flatten - tf_output_flatten), axis=0) / factor
    elif desired_norm == 'l2_norm':
        return np.sum(np.dot(np.abs(ngraph_output_flatten - tf_output_flatten), np.abs(ngraph_output_flatten - tf_output_flatten)))/factor
    elif desired_norm == 'inf_norm':
        return np.linalg.norm((ngraph_output_flatten - tf_output_flatten), np.inf)
    else:
        print ("Unsupported norm calculation")


def parse_json():
    """
        Parse the user input json file.
    """
    global frozen_graph_location
    global input_tensor_name
    global output_tensor_name
    global l1_norm_threshold
    global l2_norm_threshold
    global inf_norm_threshold
    global input_dimension

    with open(os.path.abspath(args.json_file)) as f:
        parsed_json = json.load(f)
        frozen_graph_location = parsed_json['frozen_graph_location']
        input_tensor_name = parsed_json['input_tensor_name']
        output_tensor_name = parsed_json['output_tensor_name']
        l1_norm_threshold = parsed_json['l1_norm_threshold']
        l2_norm_threshold = parsed_json['l2_norm_threshold']
        inf_norm_threshold = parsed_json['inf_norm_threshold']
        input_dimension = parsed_json['input_dimension']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_file", default="./example.json",
                        type=str, help="Model details in json format")
    args = parser.parse_args()

    parse_json()

    # Generate random input based on input_dimension
    np.random.seed(100)
    random_input = np.random.rand(1, input_dimension)

    # Run the model on ngraph
    result_ngraph = calculate_output(frozen_graph_location, "NGRAPH",
                                     random_input, input_tensor_name, output_tensor_name)

    # Run the model on tensorflow
    result_tf_graph = calculate_output(frozen_graph_location, "CPU",
                                       random_input, input_tensor_name, output_tensor_name)

    l1_norm = calculate_norm(result_ngraph, result_tf_graph,'l1_norm')
    l2_norm = calculate_norm(result_ngraph, result_tf_graph,'l2_norm')
    inf_norm = calculate_norm(result_ngraph, result_tf_graph,'inf_norm')

    if l1_norm > l1_norm_threshold:
        print ("The L1 norm %f is greater than the threshold %f " %
               (l1_norm, l1_norm_threshold))
    else:
        print ("L1 norm test passed")

    if l2_norm > l2_norm_threshold:
        print ("The L2 norm %f is greater than the threshold %f " %
               (l2_norm, l2_norm_threshold))
    else:
        print ("L2 norm test passed")

    if inf_norm > inf_norm_threshold:
        print ("The inf norm %f is greater than the threshold %f " %
               (inf_norm, inf_norm_threshold))
    else:
        print ("inf norm test passed")
    